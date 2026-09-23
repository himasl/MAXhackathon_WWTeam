from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.routes.models import RouteStatus, UserRoute, UserRouteStep


class RouteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _with_details(self) -> tuple[Any, ...]:
        return (
            joinedload(UserRoute.scenario),
            selectinload(UserRoute.steps).joinedload(UserRouteStep.scenario_step),
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

    async def get(self, route_id: UUID, user_id: UUID) -> UserRoute | None:
        query = (
            select(UserRoute)
            .where(UserRoute.id == route_id, UserRoute.user_id == user_id)
            .options(*self._with_details())
        )
        return cast(UserRoute | None, await self.session.scalar(query))

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
