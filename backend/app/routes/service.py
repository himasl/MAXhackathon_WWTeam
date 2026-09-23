from datetime import UTC, datetime
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
)
from app.scenarios.engine import RouteGenerator
from app.scenarios.service import ScenarioService
from app.sources.service import SourceService
from app.users.models import User
from app.users.repository import UserRepository
from app.users.service import UserService


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
        scenario = await self.scenario_service.get_active()
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
            completed_at=now if not generated.steps else None,
        )
        steps_by_code = {step.code: step for step in scenario.steps}
        route.steps = [
            UserRouteStep(
                scenario_step_id=steps_by_code[step.code].id,
                position=step.position,
                status=RouteStepStatus.TODO,
            )
            for step in generated.steps
        ]
        await self.repository.add(route)
        await self.session.commit()

        saved = await self.repository.get(route.id, user.id)
        if saved is None:
            raise RouteNotFoundError
        return self._route_response(saved)

    async def get_current(self, user: User) -> RouteResponse:
        route = await self.repository.get_current(user.id)
        if route is None:
            raise RouteNotFoundError
        return self._route_response(route)

    async def get_step(
        self, user: User, route_id: UUID, step_id: UUID
    ) -> RouteStepDetailResponse:
        route = await self._get_route(user, route_id)
        step = self._find_step(route, step_id)
        sources = await self.source_service.list_for_step(step.scenario_step_id)
        scenario_step = step.scenario_step
        return RouteStepDetailResponse(
            id=step.id,
            code=scenario_step.code,
            title=scenario_step.title,
            short_description=scenario_step.short_description,
            full_description=scenario_step.full_description,
            category=scenario_step.category,
            estimated_duration=scenario_step.estimated_duration,
            position=step.position,
            status=step.status,
            deadline=step.deadline,
            sources=sources,
        )

    async def complete(self, user: User, route_id: UUID, step_id: UUID) -> RouteResponse:
        route = await self._get_route(user, route_id)
        if route.status != RouteStatus.ACTIVE:
            raise InvalidOperationError("Only an active route can be updated")
        step = self._find_step(route, step_id)
        if step.status == RouteStepStatus.DONE:
            raise InvalidOperationError("Route step is already completed")

        step.status = RouteStepStatus.DONE
        step.completed_at = datetime.now(UTC)
        if all(item.status == RouteStepStatus.DONE for item in route.steps):
            route.status = RouteStatus.COMPLETED
            route.completed_at = datetime.now(UTC)
        await self.session.commit()

        saved = await self.repository.get(route.id, user.id)
        if saved is None:
            raise RouteNotFoundError
        return self._route_response(saved)

    async def reopen(self, user: User, route_id: UUID, step_id: UUID) -> RouteResponse:
        route = await self._get_route(user, route_id)
        if route.status == RouteStatus.ARCHIVED:
            raise InvalidOperationError("Archived route cannot be updated")
        step = self._find_step(route, step_id)
        if step.status != RouteStepStatus.DONE:
            raise InvalidOperationError("Only a completed route step can be reopened")

        step.status = RouteStepStatus.TODO
        step.completed_at = None
        if route.status == RouteStatus.COMPLETED:
            route.status = RouteStatus.ACTIVE
            route.completed_at = None
        await self.session.commit()

        saved = await self.repository.get(route.id, user.id)
        if saved is None:
            raise RouteNotFoundError
        return self._route_response(saved)

    async def _get_route(self, user: User, route_id: UUID) -> UserRoute:
        route = await self.repository.get(route_id, user.id)
        if route is None:
            raise RouteNotFoundError
        return route

    def _find_step(self, route: UserRoute, step_id: UUID) -> UserRouteStep:
        step = next((item for item in route.steps if item.id == step_id), None)
        if step is None:
            raise RouteStepNotFoundError
        return step

    def _route_response(self, route: UserRoute) -> RouteResponse:
        completed = sum(step.status == RouteStepStatus.DONE for step in route.steps)
        total = len(route.steps)
        progress = RouteProgress(
            completed=completed,
            total=total,
            percent=100 if total == 0 else completed * 100 // total,
        )
        return RouteResponse(
            id=route.id,
            status=route.status,
            scenario_code=route.scenario.code,
            scenario_version=route.scenario_version,
            progress=progress,
            steps=[
                RouteStepSummary(
                    id=step.id,
                    code=step.scenario_step.code,
                    title=step.scenario_step.title,
                    position=step.position,
                    status=step.status,
                    deadline=step.deadline,
                )
                for step in route.steps
            ],
        )

