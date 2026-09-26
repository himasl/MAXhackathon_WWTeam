from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.documents.models import ScenarioStepDocument
from app.routes.models import RouteStatus, RouteStepStatus, UserRoute, UserRouteStep
from app.scenarios.models import ScenarioStep


class RouteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _with_details(self) -> tuple[Any, ...]:
        return (
            joinedload(UserRoute.scenario),
            selectinload(UserRoute.steps)
            .joinedload(UserRouteStep.scenario_step)
            .selectinload(ScenarioStep.documents)
            .joinedload(ScenarioStepDocument.document),
        )

    async def archive_active(self, user_id: UUID) -> None:
        await self.session.execute(
            update(UserRoute)
            .where(UserRoute.user_id == user_id, UserRoute.status == RouteStatus.ACTIVE)
            .values(status=RouteStatus.ARCHIVED)
        )

    async def add(self, route: UserRoute) -> UserRoute:
        self.session.add(route)
        await self.session.flush()
        return route

    async def get(self, route_id: UUID, user_id: UUID, refresh: bool = False) -> UserRoute | None:
        query = (
            select(UserRoute)
            .where(UserRoute.id == route_id, UserRoute.user_id == user_id)
            .options(*self._with_details())
            .execution_options(populate_existing=refresh)
        )
        return cast(UserRoute | None, await self.session.scalar(query))

    async def get_by_step(self, step_id: UUID, user_id: UUID) -> UserRoute | None:
        query = (
            select(UserRoute)
            .join(UserRouteStep, UserRouteStep.route_id == UserRoute.id)
            .where(UserRouteStep.id == step_id, UserRoute.user_id == user_id)
            .options(*self._with_details())
        )
        return cast(UserRoute | None, await self.session.scalar(query))

    async def get_step(self, step_id: UUID) -> UserRouteStep | None:
        query = (
            select(UserRouteStep)
            .where(UserRouteStep.id == step_id)
            .options(joinedload(UserRouteStep.scenario_step))
        )
        return cast(UserRouteStep | None, await self.session.scalar(query))

    async def get_current(self, user_id: UUID) -> UserRoute | None:
        query = (
            select(UserRoute)
            .where(
                UserRoute.user_id == user_id,
                UserRoute.status != RouteStatus.ARCHIVED,
            )
            .options(*self._with_details())
            .order_by(UserRoute.created_at.desc(), UserRoute.id.desc())
            .limit(1)
        )
        return cast(UserRoute | None, await self.session.scalar(query))

    async def list_due_for_reminder(
        self, due_before: datetime, now: datetime | None = None
    ) -> list[UserRouteStep]:
        """Open steps to remind about: the deadline is near (and not snoozed further),
        or a snooze from the chat has run out."""
        current = now or datetime.now(UTC)
        not_snoozed = or_(
            UserRouteStep.snoozed_until.is_(None), UserRouteStep.snoozed_until <= current
        )
        deadline_near = and_(
            UserRouteStep.deadline.is_not(None),
            UserRouteStep.deadline <= due_before,
            not_snoozed,
        )
        snooze_over = and_(
            UserRouteStep.snoozed_until.is_not(None), UserRouteStep.snoozed_until <= current
        )
        query = (
            select(UserRouteStep)
            .join(UserRoute, UserRoute.id == UserRouteStep.route_id)
            .where(
                UserRoute.status == RouteStatus.ACTIVE,
                UserRouteStep.status.in_([RouteStepStatus.TODO, RouteStepStatus.IN_PROGRESS]),
                or_(deadline_near, snooze_over),
                UserRouteStep.reminded_at.is_(None),
            )
            .options(
                joinedload(UserRouteStep.route).joinedload(UserRoute.user),
                joinedload(UserRouteStep.scenario_step),
            )
            .order_by(UserRouteStep.deadline)
            .limit(100)
        )
        return list(await self.session.scalars(query))
