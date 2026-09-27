from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidOperationError,
    RouteNotFoundError,
    RouteStepNotFoundError,
)
from app.feedback.models import ReportKind, StepReport
from app.routes.models import RouteStatus, RouteStepStatus, UserRoute, UserRouteStep
from app.routes.repository import RouteRepository
from app.routes.schemas import (
    ChecklistGroup,
    ChecklistResponse,
    RouteProgress,
    RouteResponse,
    RouteStepDetailResponse,
    RouteStepSummary,
    SharedProgressResponse,
    SharedStep,
    StepDocumentResponse,
)
from app.scenarios.engine import RouteGenerator
from app.scenarios.service import ScenarioService
from app.sources.service import SourceService
from app.users.models import User
from app.users.repository import UserRepository
from app.users.service import UserService

OPEN_STATUSES = {RouteStepStatus.TODO, RouteStepStatus.IN_PROGRESS}
FINISHED_STATUSES = {RouteStepStatus.DONE, RouteStepStatus.SKIPPED}

# Deadlines are recommendations calculated by the service, not legal terms.
DEADLINE_ORIGIN_CALCULATED = "calculated"


def localized(item: object, field: str, lang: str) -> str:
    """Text in the requested language when a translation exists, otherwise Russian."""
    translations = getattr(item, "i18n", None) or {}
    value = (translations.get(lang) or {}).get(field)
    return str(value) if value else str(getattr(item, field))


def next_open_step(route: UserRoute) -> UserRouteStep | None:
    return next((step for step in route.steps if step.status in OPEN_STATUSES), None)


class RouteService:
    def __init__(self, session: AsyncSession, lang: str = "ru") -> None:
        self.session = session
        self.lang = lang
        self.repository = RouteRepository(session)
        self.user_repository = UserRepository(session)
        self.user_service = UserService(session)
        self.scenario_service = ScenarioService(session)
        self.source_service = SourceService(session)
        self.generator = RouteGenerator()

    async def generate(self, user: User) -> RouteResponse:
        await self.user_repository.lock(user.id)
        context = await self.user_service.get_context(user)
        scenario = await self.scenario_service.get_for(context)
        generated = self.generator.generate(
            context,
            self.scenario_service.to_definition(scenario),
        )

        await self.repository.archive_active(user.id)
        now = datetime.now(UTC)
        route = UserRoute(
            user_id=user.id,
            scenario_id=scenario.id,
            scenario_version=scenario.version,
            status=RouteStatus.COMPLETED if not generated.steps else RouteStatus.ACTIVE,
            created_at=now,
            completed_at=now if not generated.steps else None,
        )
        steps_by_code = {step.code: step for step in scenario.steps}
        route.steps = [
            UserRouteStep(
                scenario_step_id=steps_by_code[step.code].id,
                position=step.position,
                status=RouteStepStatus.TODO,
                deadline=(
                    None
                    if step.recommended_days is None
                    else now + timedelta(days=step.recommended_days)
                ),
            )
            for step in generated.steps
        ]
        await self.repository.add(route)
        await self.session.commit()
        return await self._reload(route.id, user)

    async def get_current(self, user: User) -> RouteResponse:
        return self.route_response(await self.get_current_model(user), self.lang)

    async def get_current_model(self, user: User) -> UserRoute:
        route = await self.repository.get_current(user.id)
        if route is None:
            raise RouteNotFoundError
        return route

    async def get_route_model(self, user: User, route_id: UUID) -> UserRoute:
        route = await self.repository.get(route_id, user.id)
        if route is None:
            raise RouteNotFoundError
        return route

    async def get_step(
        self, user: User, route_id: UUID, step_id: UUID
    ) -> RouteStepDetailResponse:
        route = await self.get_route_model(user, route_id)
        step = self._find_step(route, step_id)
        # Regional sources (МФЦ, ТФОМС) are linked for every region: keep only the user's one.
        profile = await self.user_repository.get_profile(user.id)
        sources = await self.source_service.list_for_step(
            step.scenario_step_id, region_code=profile.region_code if profile else None
        )
        scenario_step = step.scenario_step
        following = next(
            (
                item
                for item in route.steps
                if item.position > step.position and item.status in OPEN_STATUSES
            ),
            None,
        )
        return RouteStepDetailResponse(
            id=step.id,
            route_id=route.id,
            code=scenario_step.code,
            title=localized(scenario_step, "title", self.lang),
            short_description=localized(scenario_step, "short_description", self.lang),
            full_description=localized(scenario_step, "full_description", self.lang),
            reason=localized(scenario_step, "reason", self.lang),
            location=localized(scenario_step, "location", self.lang),
            category=scenario_step.category,
            estimated_duration=scenario_step.estimated_duration,
            is_required=scenario_step.is_required,
            position=step.position,
            status=step.status,
            deadline=step.deadline,
            deadline_origin=DEADLINE_ORIGIN_CALCULATED if step.deadline else None,
            completed_at=step.completed_at,
            documents=[
                StepDocumentResponse(
                    code=link.document.code,
                    title=localized(link.document, "title", self.lang),
                    description=localized(link.document, "description", self.lang),
                    required=link.required,
                )
                for link in sorted(
                    scenario_step.documents,
                    key=lambda item: (not item.required, item.document.title),
                )
            ],
            sources=sources,
            next_step_id=following.id if following else None,
        )

    async def complete(
        self, user: User, route_id: UUID, step_id: UUID, via: str = "app"
    ) -> RouteResponse:
        route = await self.get_route_model(user, route_id)
        if route.status != RouteStatus.ACTIVE:
            raise InvalidOperationError("Only an active route can be updated")
        step = self._find_step(route, step_id)
        if step.status == RouteStepStatus.DONE:
            raise InvalidOperationError("Route step is already completed")

        now = datetime.now(UTC)
        step.status = RouteStepStatus.DONE
        step.completed_at = now
        step.completed_via = via
        if all(item.status in FINISHED_STATUSES for item in route.steps):
            route.status = RouteStatus.COMPLETED
            route.completed_at = now
        await self.session.commit()
        return await self._reload(route.id, user)

    async def complete_from_chat(self, user: User, step_id: UUID) -> tuple[str, RouteResponse]:
        """Complete a step from the bot button. Returns the step title and updated route."""
        route = await self.repository.get_by_step(step_id, user.id)
        if route is None:
            raise RouteStepNotFoundError
        title = localized(self._find_step(route, step_id).scenario_step, "title", self.lang)
        return title, await self.complete(user, route.id, step_id, via="chat")

    async def skip(self, user: User, route_id: UUID, step_id: UUID) -> RouteResponse:
        route = await self.get_route_model(user, route_id)
        if route.status != RouteStatus.ACTIVE:
            raise InvalidOperationError("Only an active route can be updated")
        step = self._find_step(route, step_id)
        if step.status not in OPEN_STATUSES:
            raise InvalidOperationError("Only an open route step can be skipped")
        now = datetime.now(UTC)
        step.status = RouteStepStatus.SKIPPED
        step.snoozed_until = None
        if all(item.status in FINISHED_STATUSES for item in route.steps):
            route.status = RouteStatus.COMPLETED
            route.completed_at = now
        await self.session.commit()
        return await self._reload(route.id, user)

    async def reopen(self, user: User, route_id: UUID, step_id: UUID) -> RouteResponse:
        route = await self.get_route_model(user, route_id)
        if route.status == RouteStatus.ARCHIVED:
            raise InvalidOperationError("Archived route cannot be updated")
        step = self._find_step(route, step_id)
        if step.status not in FINISHED_STATUSES:
            raise InvalidOperationError("Only a completed route step can be reopened")

        step.status = RouteStepStatus.TODO
        step.completed_at = None
        step.completed_via = None
        # A reopened step gets its deadline reminder again.
        step.reminded_at = None
        if route.status == RouteStatus.COMPLETED:
            route.status = RouteStatus.ACTIVE
            route.completed_at = None
        await self.session.commit()
        return await self._reload(route.id, user)

    async def _chat_step(self, user: User, step_id: UUID) -> tuple[UserRoute, UserRouteStep]:
        route = await self.repository.get_by_step(step_id, user.id)
        if route is None:
            raise RouteStepNotFoundError
        step = self._find_step(route, step_id)
        if route.status != RouteStatus.ACTIVE or step.status not in OPEN_STATUSES:
            raise InvalidOperationError("Route step is not open")
        return route, step

    async def snooze_from_chat(self, user: User, step_id: UUID, days: int = 1) -> str:
        """"⏰ Завтра" in the chat: remind about the step again in ``days``."""
        _, step = await self._chat_step(user, step_id)
        step.snoozed_until = datetime.now(UTC) + timedelta(days=days)
        step.reminded_at = None
        await self.session.commit()
        return localized(step.scenario_step, "title", self.lang)

    async def start_from_chat(self, user: User, step_id: UUID, days: int = 3) -> str:
        """"Уже в процессе": mark the step as started and check back in ``days``."""
        _, step = await self._chat_step(user, step_id)
        step.status = RouteStepStatus.IN_PROGRESS
        step.snoozed_until = datetime.now(UTC) + timedelta(days=days)
        step.reminded_at = None
        await self.session.commit()
        return localized(step.scenario_step, "title", self.lang)

    async def checklist(self, user: User, route_id: UUID) -> ChecklistResponse:
        """Documents of the open steps grouped by where to go with them."""
        route = await self.get_route_model(user, route_id)
        groups: dict[str, ChecklistGroup] = {}
        for step in route.steps:
            if step.status not in OPEN_STATUSES or not step.scenario_step.documents:
                continue
            scenario_step = step.scenario_step
            place = localized(scenario_step, "location", self.lang) or "—"
            group = groups.setdefault(place, ChecklistGroup(place=place, steps=[], documents=[]))
            group.steps.append(localized(scenario_step, "title", self.lang))
            known = {document.code: document for document in group.documents}
            for link in scenario_step.documents:
                existing = known.get(link.document.code)
                if existing is not None:
                    existing.required = existing.required or link.required
                    continue
                document = StepDocumentResponse(
                    code=link.document.code,
                    title=localized(link.document, "title", self.lang),
                    description=localized(link.document, "description", self.lang),
                    required=link.required,
                )
                group.documents.append(document)
                known[document.code] = document
        for group in groups.values():
            group.documents.sort(key=lambda item: (not item.required, item.title))
        return ChecklistResponse(groups=list(groups.values()))

    @staticmethod
    def shared_progress(route: UserRoute, lang: str = "ru") -> SharedProgressResponse:
        response = RouteService.route_response(route, lang)
        return SharedProgressResponse(
            status=response.status,
            progress=response.progress,
            created_at=response.created_at,
            completed_at=response.completed_at,
            steps=[
                SharedStep(
                    title=summary.title,
                    category=summary.category,
                    status=summary.status,
                    completed_at=step.completed_at,
                )
                for summary, step in zip(response.steps, route.steps, strict=True)
            ],
        )

    async def report(
        self, user: User, route_id: UUID, step_id: UUID, kind: ReportKind, comment: str
    ) -> StepReport:
        """Save «Сообщить о неточности». The team gets it in the daily digest; the same note
        about the same step within a day is not stored twice."""
        route = await self.get_route_model(user, route_id)
        step = self._find_step(route, step_id)
        since = datetime.now(UTC) - timedelta(days=1)
        existing = await self.session.scalar(
            select(StepReport).where(
                StepReport.route_step_id == step.id,
                StepReport.kind == kind,
                StepReport.created_at >= since,
            )
        )
        if existing is not None:
            return existing

        profile = await self.user_repository.get_profile(user.id)
        sources = await self.source_service.list_for_step(
            step.scenario_step_id, region_code=profile.region_code if profile else None
        )
        labels = {
            ReportKind.OUTDATED: "информация устарела",
            ReportKind.NOT_APPLICABLE: "шаг не подходит",
            ReportKind.OTHER: "другое",
        }
        lines = [
            f"«{step.scenario_step.title}» — {labels[kind]}",
            (
                f"{route.scenario.code} v{route.scenario_version} · шаг {step.scenario_step.code}"
                f" · регион {profile.region_code if profile else '—'}"
            ),
        ]
        lines.extend(f"{source.url}" for source in sources)
        if comment.strip():
            lines.append(f"Комментарий: {comment.strip()}")
        report = StepReport(
            route_step_id=step.id, kind=kind, comment=comment.strip(), summary="\n".join(lines)
        )
        self.session.add(report)
        await self.session.commit()
        return report

    async def _reload(self, route_id: UUID, user: User) -> RouteResponse:
        route = await self.repository.get(route_id, user.id, refresh=True)
        if route is None:
            raise RouteNotFoundError
        return self.route_response(route, self.lang)

    def _find_step(self, route: UserRoute, step_id: UUID) -> UserRouteStep:
        step = next((item for item in route.steps if item.id == step_id), None)
        if step is None:
            raise RouteStepNotFoundError
        return step

    @staticmethod
    def route_response(route: UserRoute, lang: str = "ru") -> RouteResponse:
        # Skipped steps («Мне это не нужно») are not part of the plan any more.
        completed = sum(step.status == RouteStepStatus.DONE for step in route.steps)
        total = sum(step.status != RouteStepStatus.SKIPPED for step in route.steps)
        progress = RouteProgress(
            completed=completed,
            total=total,
            percent=100 if total == 0 else completed * 100 // total,
        )
        upcoming = next_open_step(route)
        return RouteResponse(
            id=route.id,
            status=route.status,
            scenario_code=route.scenario.code,
            scenario_version=route.scenario_version,
            created_at=route.created_at,
            completed_at=route.completed_at,
            progress=progress,
            next_step_id=upcoming.id if upcoming else None,
            steps=[
                RouteStepSummary(
                    id=step.id,
                    code=step.scenario_step.code,
                    title=localized(step.scenario_step, "title", lang),
                    short_description=localized(step.scenario_step, "short_description", lang),
                    category=step.scenario_step.category,
                    position=step.position,
                    status=step.status,
                    is_required=step.scenario_step.is_required,
                    estimated_duration=step.scenario_step.estimated_duration,
                    deadline=step.deadline,
                )
                for step in route.steps
            ],
        )
