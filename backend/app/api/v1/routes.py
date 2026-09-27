from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request, Response, status

from app.api.dependencies import CurrentUserDependency, LanguageDependency, SessionDependency
from app.api.errors import ERROR_RESPONSES
from app.auth.tokens import issue_calendar_token, issue_share_token
from app.bot.runtime import BotRuntime, format_deadline
from app.core.config import settings
from app.core.exceptions import (
    AuthUnavailableError,
    InvalidOperationError,
    RouteStepNotFoundError,
)
from app.core.rate_limit import report_limiter
from app.feedback.schemas import StepReportRequest, StepReportResponse
from app.notifications.service import NotificationService, tr
from app.routes.schemas import (
    CalendarLinkResponse,
    ChecklistResponse,
    ChecklistSentResponse,
    ReminderResponse,
    RouteResponse,
    RouteStepDetailResponse,
    ShareLinkResponse,
)
from app.routes.service import RouteService, localized, next_open_step

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
    lang: LanguageDependency,
) -> RouteResponse:
    """Build a personal route from the saved profile. A previous active route is archived."""
    route = await RouteService(session, lang).generate(user)
    background.add_task(notifications(request).route_created, user.max_user_id, route, lang)
    return route


@router.get("/current", response_model=RouteResponse)
async def get_current_route(
    user: CurrentUserDependency,
    session: SessionDependency,
    lang: LanguageDependency,
) -> RouteResponse:
    return await RouteService(session, lang).get_current(user)


@router.get("/{route_id}/steps/{step_id}", response_model=RouteStepDetailResponse)
async def get_route_step(
    route_id: UUID,
    step_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
    lang: LanguageDependency,
) -> RouteStepDetailResponse:
    return await RouteService(session, lang).get_step(user, route_id, step_id)


@router.post("/{route_id}/steps/{step_id}/complete", response_model=RouteResponse)
async def complete_route_step(
    request: Request,
    background: BackgroundTasks,
    route_id: UUID,
    step_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
    lang: LanguageDependency,
) -> RouteResponse:
    route = await RouteService(session, lang).complete(user, route_id, step_id, via="app")
    background.add_task(notifications(request).step_completed, user.max_user_id, route, lang)
    return route


@router.post("/{route_id}/steps/{step_id}/skip", response_model=RouteResponse)
async def skip_route_step(
    route_id: UUID,
    step_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
    lang: LanguageDependency,
) -> RouteResponse:
    """«Мне это не нужно»: the step leaves the plan and no longer counts in the progress.
    It can be returned with /reopen."""
    return await RouteService(session, lang).skip(user, route_id, step_id)


@router.post("/{route_id}/steps/{step_id}/reopen", response_model=RouteResponse)
async def reopen_route_step(
    route_id: UUID,
    step_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
    lang: LanguageDependency,
) -> RouteResponse:
    return await RouteService(session, lang).reopen(user, route_id, step_id)


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
        user.max_user_id,
        step.id,
        localized(step.scenario_step, "title", user.lang),
        format_deadline(step.deadline),
        user.lang,
    )
    return ReminderResponse(sent=sent, step_id=step.id)


CALENDAR_LINK_TTL_SECONDS = 30 * 24 * 3600


@router.post("/{route_id}/steps/{step_id}/calendar-link", response_model=CalendarLinkResponse)
async def create_calendar_link(
    request: Request,
    route_id: UUID,
    step_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> CalendarLinkResponse:
    """Signed link to an .ics file with the step's recommended deadline.

    The link opens in the phone's browser or calendar app, so it carries its own token
    instead of the Authorization header. It grants access to this event only.
    """
    route = await RouteService(session).get_route_model(user, route_id)
    step = next((item for item in route.steps if item.id == step_id), None)
    if step is None:
        raise RouteStepNotFoundError
    if step.deadline is None:
        raise InvalidOperationError("Route step has no recommended deadline")
    if not settings.signing_key:
        raise AuthUnavailableError("Calendar links are not configured")
    token = issue_calendar_token(step.id, settings.signing_key, CALENDAR_LINK_TTL_SECONDS)
    base = settings.public_url or str(request.base_url).rstrip("/")
    return CalendarLinkResponse(
        url=f"{base}/api/v1/calendar/{token}.ics", expires_in=CALENDAR_LINK_TTL_SECONDS
    )


@router.get("/{route_id}/checklist", response_model=ChecklistResponse)
async def get_checklist(
    route_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
    lang: LanguageDependency,
) -> ChecklistResponse:
    """What to take with you: documents of the open steps grouped by place."""
    return await RouteService(session, lang).checklist(user, route_id)


@router.post("/{route_id}/checklist/send", response_model=ChecklistSentResponse)
async def send_checklist(
    request: Request,
    route_id: UUID,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> ChecklistSentResponse:
    """Send the checklist to the user's MAX chat, to have it at hand in the queue."""
    lang = user.lang
    checklist = await RouteService(session, lang).checklist(user, route_id)
    if not checklist.groups:
        return ChecklistSentResponse(sent=False)
    optional = tr(lang, " (если есть)", " (if you have it)")
    lines = [tr(lang, "Что взять с собой", "What to take with you")]
    for group in checklist.groups:
        lines.append(f"\n📍 {group.place} — {', '.join(group.steps)}")
        lines.extend(
            f"• {item.title}{'' if item.required else optional}" for item in group.documents
        )
    sent = await notifications(request).send_text(user.max_user_id, "\n".join(lines), lang)
    return ChecklistSentResponse(sent=sent)


SHARE_LINK_TTL_SECONDS = 90 * 24 * 3600


@router.post("/share", response_model=ShareLinkResponse)
async def create_share_link(
    request: Request, user: CurrentUserDependency, session: SessionDependency
) -> ShareLinkResponse:
    """Read-only link to the route progress for parents: step titles and statuses only,
    without answers, region, university or contacts. Revoke with DELETE /routes/share."""
    await RouteService(session).get_current_model(user)
    if not settings.signing_key:
        raise AuthUnavailableError("Share links are not configured")
    token = issue_share_token(
        user.id, user.share_version, settings.signing_key, SHARE_LINK_TTL_SECONDS
    )
    base = settings.public_url or str(request.base_url).rstrip("/")
    return ShareLinkResponse(url=f"{base}/?share={token}", expires_in=SHARE_LINK_TTL_SECONDS)


@router.delete("/share", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def revoke_share_links(user: CurrentUserDependency, session: SessionDependency) -> Response:
    """Revoke every progress link issued before."""
    user.share_version += 1
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{route_id}/steps/{step_id}/report",
    response_model=StepReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def report_step(
    route_id: UUID,
    step_id: UUID,
    payload: StepReportRequest,
    user: CurrentUserDependency,
    session: SessionDependency,
) -> StepReportResponse:
    """«Сообщить о неточности». Notes reach the team (SUPPORT_MAX_USER_IDS) once a day in a
    digest with the step, scenario version, region and sources. A repeat of the same note
    about the same step within a day is accepted but not stored twice."""
    report_limiter.check(str(user.id))
    report = await RouteService(session).report(
        user, route_id, step_id, payload.kind, payload.comment
    )
    return StepReportResponse(id=report.id, kind=report.kind)
