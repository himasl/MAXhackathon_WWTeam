"""The team panel: business metrics, editing regional sources, users' reports.

Metrics are aggregates only. Reviewer test accounts and the team itself are excluded,
so the numbers show how real students use the service."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import access
from app.admin.activity import today
from app.admin.models import UserActivity
from app.admin.schemas import (
    ActivityBlock,
    AdminOverview,
    AdminReport,
    AdminSource,
    Count,
    DataBlock,
    DayActivity,
    EngagementBlock,
    FunnelStage,
    SourceUpdate,
    StepProblem,
    UsersBlock,
)
from app.core.config import settings
from app.core.exceptions import ApplicationError
from app.feedback.models import StepReport
from app.regions.catalog import load_regions
from app.routes.models import RouteStatus, RouteStepStatus, UserRoute, UserRouteStep
from app.scenarios.models import ScenarioStep
from app.sources.models import Source, scenario_step_sources
from app.stats.service import StatsService
from app.universities.models import University
from app.users.models import User, UserProfile

STALE_SOURCE_DAYS = 90
SECONDS_PER_DAY = 86400
HOUSING_TITLES = {
    "DORMITORY": "Общежитие",
    "RENT": "Снимает жильё",
    "RELATIVES": "У родственников",
    "OTHER": "Другое",
}
LANGUAGE_TITLES = {"ru": "Русский", "en": "English"}
KIND_BY_PREFIX = {
    "region_mfc_": "mfc",
    "region_tfoms_": "tfoms",
    "region_transport_": "transport",
}


class SourceNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("SOURCE_NOT_FOUND", "Source was not found", 404)


class ReportNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("REPORT_NOT_FOUND", "Report was not found", 404)


def _rate(part: int, whole: int) -> float:
    return round(part / whole, 3) if whole else 0.0


def source_kind(source: Source) -> str:
    for prefix, kind in KIND_BY_PREFIX.items():
        if (source.code or "").startswith(prefix):
            return kind
    return "regional" if source.region_code else "federal"


def excluded_ids() -> list[int]:
    """Reviewer test accounts and the team: not counted as students."""
    return sorted(set(settings.test_access_tokens.values()) | access.admin_ids())


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.excluded = excluded_ids()

    # -- metrics ----------------------------------------------------------------------

    def _real(self, query: Select[Any]) -> Select[Any]:
        return query.where(User.max_user_id.not_in(self.excluded)) if self.excluded else query

    async def _int(self, query: Select[Any]) -> int:
        return int(await self.session.scalar(self._real(query)) or 0)

    async def overview(self, now: datetime | None = None) -> AdminOverview:
        now = now or datetime.now(UTC)
        stats = await StatsService(self.session, self.excluded).collect()
        users = await self._users(now)
        funnel = await self._funnel(users)
        steps = await self._steps()
        route_days = await self.session.scalar(
            self._real(
                select(
                    func.percentile_cont(0.5).within_group(
                        func.extract("epoch", UserRoute.completed_at - UserRoute.created_at)
                    )
                )
                .select_from(UserRoute)
                .join(User, User.id == UserRoute.user_id)
                .where(UserRoute.status == RouteStatus.COMPLETED)
            )
        )
        routes_live = await self._int(
            select(func.count(UserRoute.id))
            .select_from(UserRoute)
            .join(User, User.id == UserRoute.user_id)
            .where(UserRoute.status != RouteStatus.ARCHIVED)
        )
        steps_live = await self._int(
            select(func.count(UserRouteStep.id))
            .select_from(UserRouteStep)
            .join(UserRoute, UserRoute.id == UserRouteStep.route_id)
            .join(User, User.id == UserRoute.user_id)
            .where(UserRoute.status != RouteStatus.ARCHIVED)
        )
        skipped = await self._int(
            select(func.count(UserRouteStep.id))
            .select_from(UserRouteStep)
            .join(UserRoute, UserRoute.id == UserRouteStep.route_id)
            .join(User, User.id == UserRoute.user_id)
            .where(UserRouteStep.status == RouteStepStatus.SKIPPED)
        )
        return AdminOverview(
            generated_at=now,
            users=users,
            activity=await self._activity(now),
            funnel=funnel,
            engagement=EngagementBlock(
                steps_done=stats.steps.done,
                steps_skipped=skipped,
                done_from_chat_share=_rate(stats.steps.done_from_chat, stats.steps.done),
                reminders_sent=stats.steps.reminders_sent,
                reminder_conversion=_rate(
                    stats.steps.done_after_reminder, stats.steps.reminders_sent
                ),
                avg_steps_per_route=round(steps_live / routes_live, 1) if routes_live else 0.0,
                completion_rate=stats.routes.completion_rate,
                route_median_days=None
                if route_days is None
                else round(float(route_days) / SECONDS_PER_DAY, 1),
                registration_median_days=stats.registration_median_days,
            ),
            by_region=await self._by_region(),
            by_university=await self._by_university(),
            by_scenario=[
                Count(code=item.code, title=item.title, users=item.routes, completed=item.completed)
                for item in stats.by_scenario
            ],
            by_housing=await self._by_profile_field(UserProfile.housing_type, HOUSING_TITLES),
            by_language=await self._by_language(),
            problem_steps=steps,
            data=await self._data(now),
        )

    async def _users(self, now: datetime) -> UsersBlock:
        base = select(func.count(User.id)).select_from(User)
        return UsersBlock(
            total=await self._int(base),
            with_profile=await self._int(base.join(UserProfile, UserProfile.user_id == User.id)),
            with_route=await self._int(
                select(func.count(distinct(UserRoute.user_id)))
                .select_from(UserRoute)
                .join(User, User.id == UserRoute.user_id)
            ),
            new_7d=await self._int(base.where(User.created_at >= now - timedelta(days=7))),
            new_30d=await self._int(base.where(User.created_at >= now - timedelta(days=30))),
        )

    async def _funnel(self, users: UsersBlock) -> list[FunnelStage]:
        done = UserRouteStep.status == RouteStepStatus.DONE
        first_done = await self._int(
            select(func.count(distinct(UserRoute.user_id)))
            .select_from(UserRouteStep)
            .join(UserRoute, UserRoute.id == UserRouteStep.route_id)
            .join(User, User.id == UserRoute.user_id)
            .where(done)
        )
        completed = await self._int(
            select(func.count(distinct(UserRoute.user_id)))
            .select_from(UserRoute)
            .join(User, User.id == UserRoute.user_id)
            .where(UserRoute.status == RouteStatus.COMPLETED)
        )
        return [
            FunnelStage(code="opened", title="Открыли приложение", users=users.total),
            FunnelStage(code="profile", title="Заполнили анкету", users=users.with_profile),
            FunnelStage(code="route", title="Получили маршрут", users=users.with_route),
            FunnelStage(code="first_step", title="Закрыли первое дело", users=first_done),
            FunnelStage(code="completed", title="Прошли маршрут до конца", users=completed),
        ]

    async def _activity(self, now: datetime) -> ActivityBlock:
        day = today(now)
        month_start = day - timedelta(days=29)

        def active_since(start: Any, channel: str | None = None) -> Select[Any]:
            query = (
                select(func.count(distinct(UserActivity.user_id)))
                .select_from(UserActivity)
                .join(User, User.id == UserActivity.user_id)
                .where(UserActivity.day >= start)
            )
            return query if channel is None else query.where(UserActivity.channel == channel)

        dau = await self._int(active_since(day))
        wau = await self._int(active_since(day - timedelta(days=6)))
        mau = await self._int(active_since(month_start))
        bot_users = await self._int(active_since(month_start, "bot"))

        days_per_user = (
            select(UserActivity.user_id, func.count(distinct(UserActivity.day)).label("days"))
            .join(User, User.id == UserActivity.user_id)
            .group_by(UserActivity.user_id)
        )
        rows = (await self.session.execute(self._real(days_per_user))).all()
        returning = sum(1 for row in rows if int(row[1]) > 1)

        daily_rows = (
            await self.session.execute(
                self._real(
                    select(
                        UserActivity.day,
                        func.count(distinct(UserActivity.user_id)),
                        func.count(distinct(UserActivity.user_id)).filter(
                            UserActivity.channel == "app"
                        ),
                        func.count(distinct(UserActivity.user_id)).filter(
                            UserActivity.channel == "bot"
                        ),
                    )
                    .join(User, User.id == UserActivity.user_id)
                    .where(UserActivity.day >= month_start)
                    .group_by(UserActivity.day)
                )
            )
        ).all()
        by_day = {row[0]: row for row in daily_rows}
        daily = []
        for offset in range(30):
            current = month_start + timedelta(days=offset)
            row = by_day.get(current)
            daily.append(
                DayActivity(
                    day=current,
                    total=int(row[1]) if row else 0,
                    app=int(row[2]) if row else 0,
                    bot=int(row[3]) if row else 0,
                )
            )
        return ActivityBlock(
            dau=dau,
            wau=wau,
            mau=mau,
            stickiness=_rate(dau, mau),
            returning_share=_rate(returning, len(rows)),
            bot_share=_rate(bot_users, mau),
            daily=daily,
        )

    def _profile_counts(self, key: Any, title: Any) -> Select[Any]:
        completed = func.count(distinct(UserRoute.user_id)).filter(
            UserRoute.status == RouteStatus.COMPLETED
        )
        return (
            select(key, title, func.count(distinct(UserProfile.user_id)), completed)
            .select_from(UserProfile)
            .join(User, User.id == UserProfile.user_id)
            .outerjoin(UserRoute, UserRoute.user_id == User.id)
            .group_by(key, title)
            .order_by(func.count(distinct(UserProfile.user_id)).desc(), key)
        )

    async def _by_region(self) -> list[Count]:
        titles = {region.code: region.title for region in load_regions()}
        rows = (
            await self.session.execute(
                self._real(self._profile_counts(UserProfile.region_code, UserProfile.region_code))
            )
        ).all()
        return [
            Count(code=row[0], title=titles.get(row[0], row[0]), users=row[2], completed=row[3])
            for row in rows[:15]
        ]

    async def _by_university(self) -> list[Count]:
        query = self._profile_counts(University.code, University.short_title).join(
            University, University.code == UserProfile.university_code
        )
        rows = (await self.session.execute(self._real(query))).all()
        return [
            Count(code=row[0], title=row[1], users=row[2], completed=row[3]) for row in rows[:10]
        ]

    async def _by_profile_field(self, field: Any, titles: dict[str, str]) -> list[Count]:
        rows = (await self.session.execute(self._real(self._profile_counts(field, field)))).all()
        return [
            Count(
                code=str(row[0]),
                title=titles.get(str(row[0]), str(row[0])),
                users=row[2],
                completed=row[3],
            )
            for row in rows
        ]

    async def _by_language(self) -> list[Count]:
        rows = (
            await self.session.execute(
                self._real(
                    select(User.lang, func.count(User.id))
                    .select_from(User)
                    .group_by(User.lang)
                    .order_by(func.count(User.id).desc())
                )
            )
        ).all()
        return [
            Count(code=row[0], title=LANGUAGE_TITLES.get(row[0], row[0]), users=row[1])
            for row in rows
        ]

    async def _steps(self) -> list[StepProblem]:
        """Steps where students get stuck: the most open (neither done nor skipped) first."""
        reports = (
            select(StepReport.route_step_id, func.count(StepReport.id).label("reports"))
            .group_by(StepReport.route_step_id)
            .subquery()
        )
        done = UserRouteStep.status == RouteStepStatus.DONE
        rows = (
            await self.session.execute(
                self._real(
                    select(
                        ScenarioStep.code,
                        ScenarioStep.title,
                        func.count(UserRouteStep.id),
                        func.count(UserRouteStep.id).filter(done),
                        func.count(UserRouteStep.id).filter(
                            UserRouteStep.status == RouteStepStatus.SKIPPED
                        ),
                        func.coalesce(func.sum(reports.c.reports), 0),
                    )
                    .select_from(UserRouteStep)
                    .join(ScenarioStep, ScenarioStep.id == UserRouteStep.scenario_step_id)
                    .join(UserRoute, UserRoute.id == UserRouteStep.route_id)
                    .join(User, User.id == UserRoute.user_id)
                    .outerjoin(reports, reports.c.route_step_id == UserRouteStep.id)
                    .where(UserRoute.status != RouteStatus.ARCHIVED)
                    .group_by(ScenarioStep.code, ScenarioStep.title)
                )
            )
        ).all()
        steps = [
            StepProblem(
                code=row[0],
                title=row[1],
                in_routes=int(row[2]),
                done=int(row[3]),
                skipped=int(row[4]),
                reports=int(row[5]),
                completion_rate=_rate(int(row[3]), int(row[2])),
            )
            for row in rows
        ]
        # Most students still stuck first (not done and not skipped), then reports.
        steps.sort(
            key=lambda step: (
                -(step.in_routes - step.done - step.skipped),
                -step.reports,
                step.completion_rate,
            )
        )
        return steps[:10]

    async def _data(self, now: datetime) -> DataBlock:
        regional = Source.region_code.is_not(None)
        stale_before = now - timedelta(days=STALE_SOURCE_DAYS)
        row = (
            await self.session.execute(
                select(
                    func.count(Source.id).filter(regional),
                    func.count(Source.id).filter(
                        and_(
                            Source.source_type == "OFFICIAL",
                            (Source.checked_at.is_(None)) | (Source.checked_at < stale_before),
                        )
                    ),
                    func.count(Source.id).filter(Source.edited_at.is_not(None)),
                )
            )
        ).one()
        open_reports = int(
            await self.session.scalar(
                select(func.count(StepReport.id)).where(StepReport.resolved_at.is_(None))
            )
            or 0
        )
        return DataBlock(
            regional_sources=int(row[0]),
            stale_sources=int(row[1]),
            edited_sources=int(row[2]),
            open_reports=open_reports,
        )

    # -- sources ----------------------------------------------------------------------

    async def sources(
        self,
        region_code: str | None = None,
        kind: str | None = None,
        stale_only: bool = False,
        now: datetime | None = None,
    ) -> list[AdminSource]:
        now = now or datetime.now(UTC)
        titles = {region.code: region.title for region in load_regions()}
        steps = (
            select(scenario_step_sources.c.source_id, func.count().label("steps"))
            .group_by(scenario_step_sources.c.source_id)
            .subquery()
        )
        query = (
            select(Source, func.coalesce(steps.c.steps, 0))
            .outerjoin(steps, steps.c.source_id == Source.id)
            .where(Source.source_type == "OFFICIAL")
            .order_by(Source.region_code.nulls_first(), Source.code)
        )
        if region_code:
            query = query.where(Source.region_code == region_code)
        rows = (await self.session.execute(query)).all()
        stale_before = now - timedelta(days=STALE_SOURCE_DAYS)
        result = []
        for source, step_count in rows:
            item_kind = source_kind(source)
            stale = source.checked_at is None or source.checked_at < stale_before
            if kind and item_kind != kind:
                continue
            if stale_only and not stale:
                continue
            result.append(
                AdminSource(
                    id=source.id,
                    code=source.code,
                    kind=item_kind,
                    title=source.title,
                    organization=source.organization,
                    url=source.url,
                    region_code=source.region_code,
                    region_title=titles.get(source.region_code or ""),
                    checked_at=source.checked_at,
                    stale=stale,
                    edited_at=source.edited_at,
                    steps=int(step_count),
                )
            )
        return result

    async def update_source(
        self, source_id: UUID, payload: SourceUpdate, editor: int
    ) -> AdminSource:
        source = await self.session.get(Source, source_id)
        if source is None or source.source_type != "OFFICIAL":
            raise SourceNotFoundError()
        now = datetime.now(UTC)
        if payload.url is not None:
            source.url = str(payload.url)
        if payload.organization is not None:
            source.organization = payload.organization.strip()
        if payload.title is not None:
            source.title = payload.title.strip()
        if payload.mark_checked:
            source.checked_at = now
        source.edited_at = now
        source.edited_by = editor
        await self.session.commit()
        items = await self.sources(region_code=source.region_code, now=now)
        return next(item for item in items if item.id == source.id)

    # -- reports ----------------------------------------------------------------------

    async def reports(self, resolved: bool = False) -> list[AdminReport]:
        query = (
            select(StepReport, ScenarioStep.title, UserProfile.region_code)
            .join(UserRouteStep, UserRouteStep.id == StepReport.route_step_id)
            .join(ScenarioStep, ScenarioStep.id == UserRouteStep.scenario_step_id)
            .join(UserRoute, UserRoute.id == UserRouteStep.route_id)
            .outerjoin(UserProfile, UserProfile.user_id == UserRoute.user_id)
            .where(
                StepReport.resolved_at.is_not(None)
                if resolved
                else StepReport.resolved_at.is_(None)
            )
            .order_by(StepReport.created_at.desc())
            .limit(100)
        )
        rows = (await self.session.execute(query)).all()
        return [
            AdminReport(
                id=report.id,
                kind=report.kind,
                comment=report.comment,
                summary=report.summary,
                step_title=title,
                region_code=region,
                created_at=report.created_at,
                resolved_at=report.resolved_at,
            )
            for report, title, region in rows
        ]

    async def set_resolved(self, report_id: UUID, resolved: bool) -> None:
        report = await self.session.get(StepReport, report_id)
        if report is None:
            raise ReportNotFoundError()
        report.resolved_at = datetime.now(UTC) if resolved else None
        await self.session.commit()
