from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import CurrentUserDependency, SessionDependency
from app.api.errors import ERROR_RESPONSES
from app.routes.schemas import RouteResponse, RouteStepDetailResponse
from app.routes.service import RouteService

router = APIRouter(prefix="/routes", tags=["routes"], responses=ERROR_RESPONSES)


@router.post("", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    user: CurrentUserDependency,
    session: SessionDependency,
) -> RouteResponse:
    return await RouteService(session).generate(user)


@router.get("/current", response_model=RouteResponse)
async def get_current_route(
    user: CurrentUserDependency,
    session: SessionDependency,
) -> RouteResponse:
    return await RouteService(session).get_current(user)


@router.get("/{route_id}/steps/{step_id}", response_model=RouteStepDetailResponse)
async def get_route_step(
    route_id: UUID,
    step_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> RouteStepDetailResponse:
    return await RouteService(session).get_step(user, route_id, step_id)


@router.post("/{route_id}/steps/{step_id}/complete", response_model=RouteResponse)
async def complete_route_step(
    route_id: UUID,
    step_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> RouteResponse:
    return await RouteService(session).complete(user, route_id, step_id)


@router.post("/{route_id}/steps/{step_id}/reopen", response_model=RouteResponse)
async def reopen_route_step(
    route_id: UUID,
    step_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> RouteResponse:
    return await RouteService(session).reopen(user, route_id, step_id)

