from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import Response

from app.api.dependencies import SessionDependency
from app.api.errors import ERROR_RESPONSES
from app.auth.tokens import TokenError, verify_calendar_token
from app.calendar.ics import step_event
from app.core.config import settings
from app.core.exceptions import RouteStepNotFoundError
from app.routes.repository import RouteRepository
from app.stats.schemas import StatsResponse
from app.stats.service import StatsService

router = APIRouter(tags=["public"], responses=ERROR_RESPONSES)
MOSCOW = ZoneInfo("Europe/Moscow")


@router.get("/stats", response_model=StatsResponse)
async def get_stats(session: SessionDependency) -> StatsResponse:
    """Anonymous pilot metrics: routes, completion rate, steps done from the chat,
    reminders and the median number of days until registration is done."""
    return await StatsService(session).collect()


@router.get(
    "/calendar/{token}.ics",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}}},
)
async def get_calendar_file(token: str, session: SessionDependency) -> Response:
    """Calendar file for a step deadline, addressed by a signed link token."""
    try:
        step_id = verify_calendar_token(token, settings.signing_key)
    except TokenError as error:
        raise RouteStepNotFoundError from error
    step = await RouteRepository(session).get_step(step_id)
    if step is None or step.deadline is None:
        raise RouteStepNotFoundError

    body = step_event(
        uid=str(step.id),
        title=step.scenario_step.title,
        description=(
            f"{step.scenario_step.short_description}\n"
            "Рекомендуемый срок рассчитан сервисом «Маршрут» и не является юридическим "
            "требованием."
        ),
        day=step.deadline.astimezone(MOSCOW).date(),
        url=settings.mini_app_url,
    )
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="marshrut-step.ics"'},
    )
