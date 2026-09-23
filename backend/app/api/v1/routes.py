from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request, status

from app.api.dependencies import CurrentUserDependency, SessionDependency
from app.api.errors import ERROR_RESPONSES
from app.bot.runtime import BotRuntime, format_deadline
from app.notifications.service import NotificationService
from app.routes.schemas import ReminderResponse, RouteResponse, RouteStepDetailResponse
from app.routes.service import RouteService, next_open_step

router = APIRouter(prefix="/routes", tags=["routes"], responses=ERROR_RESPONSES)


def notifications(request: Request) -> NotificationService:
    runtime: BotRuntime = request.app.state.bot
    return runtime.notifications


@router.post("", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    request: Request,
    background: BackgroundTasks,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> RouteResponse:
    """Build a personal route from the saved profile. A previous active route is archived."""
    route = await RouteService(session).generate(user)
    background.add_task(notifications(request).route_created, user.max_user_id, route)
    return route


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
    request: Request,
    background: BackgroundTasks,
    route_id: UUID,
    step_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> RouteResponse:
    route = await RouteService(session).complete(user, route_id, step_id)
    background.add_task(notifications(request).step_completed, user.max_user_id, route)
    return route


@router.post("/{route_id}/steps/{step_id}/reopen", response_model=RouteResponse)
async def reopen_route_step(
    route_id: UUID,
    step_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> RouteResponse:
    return await RouteService(session).reopen(user, route_id, step_id)


@router.post("/{route_id}/remind", response_model=ReminderResponse)
async def send_reminder(
    request: Request,
    route_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> ReminderResponse:
    """Send the next open step to the user's MAX chat right now.

    ``sent`` is false when the bot is not configured or MAX did not accept the message.
    """
    route = await RouteService(session).get_route_model(user, route_id)
    step = next_open_step(route)
    if step is None:
        return ReminderResponse(sent=False, step_id=None)
    sent = await notifications(request).reminder(
        user.max_user_id, step.id, step.scenario_step.title, format_deadline(step.deadline)
    )
    return ReminderResponse(sent=sent, step_id=step.id)
