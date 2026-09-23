from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidOperationError,
    RouteNotFoundError,
    RouteStepNotFoundError,
)
from app.routes.models import RouteStatus, RouteStepStatus, UserRoute, UserRouteStep
from app.routes.repository import RouteRepository
from app.routes.schemas import (
    RouteProgress,
    RouteResponse,
    RouteStepDetailResponse,
    RouteStepSummary,
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


def next_open_step(route: UserRoute) -> UserRouteStep | None:
    return next((step for step in route.steps if step.status in OPEN_STATUSES), None)


class RouteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
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
        return self.route_response(await self.get_current_model(user))

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
        sources = await self.source_service.list_for_step(step.scenario_step_id)
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
            title=scenario_step.title,
            short_description=scenario_step.short_description,
            full_description=scenario_step.full_description,
            reason=scenario_step.reason,
            location=scenario_step.location,
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
                    title=link.document.title,
                    description=link.document.description,
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
        title = self._find_step(route, step_id).scenario_step.title
        return title, await self.complete(user, route.id, step_id, via="chat")

    async def reopen(self, user: User, route_id: UUID, step_id: UUID) -> RouteResponse:
        route = await self.get_route_model(user, route_id)
        if route.status == RouteStatus.ARCHIVED:
            raise InvalidOperationError("Archived route cannot be updated")
        step = self._find_step(route, step_id)
        if step.status != RouteStepStatus.DONE:
            raise InvalidOperationError("Only a completed route step can be reopened")

        step.status = RouteStepStatus.TODO
        step.completed_at = None
        step.completed_via = None
        if route.status == RouteStatus.COMPLETED:
            route.status = RouteStatus.ACTIVE
            route.completed_at = None
        await self.session.commit()
        return await self._reload(route.id, user)

    async def _reload(self, route_id: UUID, user: User) -> RouteResponse:
        route = await self.repository.get(route_id, user.id, refresh=True)
        if route is None:
            raise RouteNotFoundError
        return self.route_response(route)

    def _find_step(self, route: UserRoute, step_id: UUID) -> UserRouteStep:
        step = next((item for item in route.steps if item.id == step_id), None)
        if step is None:
            raise RouteStepNotFoundError
        return step

    @staticmethod
    def route_response(route: UserRoute) -> RouteResponse:
        completed = sum(step.status == RouteStepStatus.DONE for step in route.steps)
        total = len(route.steps)
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
                    title=step.scenario_step.title,
                    short_description=step.scenario_step.short_description,
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
