"""Anonymous pilot metrics: completion, completion from the chat, reminders, time to
registration. Reviewer test accounts are excluded so the numbers reflect real users."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import access
from app.core.config import settings
from app.feedback.models import StepReport
from app.routes.models import RouteStatus, RouteStepStatus, UserRoute, UserRouteStep
from app.scenarios.models import Scenario, ScenarioStep, StepCategory
from app.stats.schemas import GroupStats, RouteStats, StatsResponse, StepStats
from app.universities.models import University
from app.users.models import User, UserProfile

SECONDS_PER_DAY = 86400


class StatsService:
    def __init__(self, session: AsyncSession, excluded: list[int] | None = None) -> None:
        self.session = session
        # Reviewer test accounts and the team (SUPPORT_MAX_USER_IDS) are not students.
        self.excluded = (
            excluded
            if excluded is not None
            else sorted(set(settings.test_access_tokens.values()) | access.admin_ids())
        )

    def _real_users(self, query: Select[Any]) -> Select[Any]:
        if not self.excluded:
            return query
        return query.where(User.max_user_id.not_in(self.excluded))

    async def _scalar(self, query: Select[Any]) -> int:
        return int(await self.session.scalar(query) or 0)

    async def collect(self) -> StatsResponse:
        users = await self._scalar(self._real_users(select(func.count(UserProfile.id)).join(User)))

        route_base = select(UserRoute).join(User, User.id == UserRoute.user_id)
        created = await self._scalar(
            self._real_users(route_base.with_only_columns(func.count(UserRoute.id)))
        )
        rows = (
            await self.session.execute(
                self._real_users(
                    route_base.with_only_columns(UserRoute.status, func.count())
                    .where(UserRoute.status != RouteStatus.ARCHIVED)
                    .group_by(UserRoute.status)
                )
            )
        ).all()
        status_counts: dict[RouteStatus, int] = {row[0]: int(row[1]) for row in rows}
        active = int(status_counts.get(RouteStatus.ACTIVE, 0))
        completed = int(status_counts.get(RouteStatus.COMPLETED, 0))

        step_base = (
            select(UserRouteStep)
            .join(UserRoute, UserRoute.id == UserRouteStep.route_id)
            .join(User, User.id == UserRoute.user_id)
        )
        done = UserRouteStep.status == RouteStepStatus.DONE
        row = (
            await self.session.execute(
                self._real_users(
                    step_base.with_only_columns(
                        func.count().filter(done),
                        func.count().filter(and_(done, UserRouteStep.completed_via == "chat")),
                        func.count().filter(UserRouteStep.reminded_at.is_not(None)),
                        func.count().filter(
                            and_(done, UserRouteStep.completed_at >= UserRouteStep.reminded_at)
                        ),
                    )
                )
            )
        ).one()

        reported = await self._scalar(
            self._real_users(
                select(func.count(StepReport.id))
                .join(UserRouteStep, UserRouteStep.id == StepReport.route_step_id)
                .join(UserRoute, UserRoute.id == UserRouteStep.route_id)
                .join(User, User.id == UserRoute.user_id)
            )
        )

        registration_seconds = await self.session.scalar(
            self._real_users(
                step_base.join(ScenarioStep, ScenarioStep.id == UserRouteStep.scenario_step_id)
                .with_only_columns(
                    func.percentile_cont(0.5).within_group(
                        func.extract("epoch", UserRouteStep.completed_at - UserRoute.created_at)
                    )
                )
                .where(done, ScenarioStep.category == StepCategory.REGISTRATION)
            )
        )

        return StatsResponse(
            generated_at=datetime.now(UTC),
            users=users,
            routes=RouteStats(
                created=created,
                active=active,
                completed=completed,
                completion_rate=round(completed / (active + completed), 3)
                if active + completed
                else 0.0,
            ),
            steps=StepStats(
                done=int(row[0]),
                done_from_chat=int(row[1]),
                reminders_sent=int(row[2]),
                done_after_reminder=int(row[3]),
                reported=reported,
            ),
            registration_median_days=None
            if registration_seconds is None
            else round(float(registration_seconds) / SECONDS_PER_DAY, 1),
            by_scenario=await self._grouped(Scenario.code, Scenario.title, Scenario),
            by_university=await self._grouped(University.code, University.short_title, None),
        )

    async def _grouped(
        self, code: Any, title: Any, scenario: type[Scenario] | None
    ) -> list[GroupStats]:
        query = (
            select(
                code,
                title,
                func.count(UserRoute.id),
                func.count(case((UserRoute.status == RouteStatus.COMPLETED, 1))),
            )
            .select_from(UserRoute)
            .join(User, User.id == UserRoute.user_id)
            .where(UserRoute.status != RouteStatus.ARCHIVED)
            .group_by(code, title)
            .order_by(code)
        )
        if scenario is not None:
            query = query.join(Scenario, Scenario.id == UserRoute.scenario_id)
        else:
            query = query.join(UserProfile, UserProfile.user_id == User.id).join(
                University, University.code == UserProfile.university_code
            )
        rows = (await self.session.execute(self._real_users(query))).all()
        return [
            GroupStats(code=row[0], title=row[1], routes=int(row[2]), completed=int(row[3]))
            for row in rows
        ]
