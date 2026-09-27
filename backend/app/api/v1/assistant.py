from fastapi import APIRouter

from app.api.dependencies import CurrentUserDependency, LanguageDependency, SessionDependency
from app.api.errors import ERROR_RESPONSES
from app.assistant.schemas import AskRequest, AskResponse
from app.assistant.service import AssistantService

router = APIRouter(tags=["assistant"], responses=ERROR_RESPONSES)


@router.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest,
    user: CurrentUserDependency,
    session: SessionDependency,
    lang: LanguageDependency,
) -> AskResponse:
    """A question about the route or a step. Answered by the RAG service (``RAG_URL``)
    or, without it, by the built-in search over the student's route; every answer comes
    with official sources."""
    return await AssistantService(session, lang).ask(user, payload.question, payload.step_id)
