"""Answers a student's question in the app («Задать вопрос») and in the bot (free text).

The request carries the student's context: region, citizenship, university, the current
step and the whole route with official sources. The external RAG service answers first
when ``RAG_URL`` is set; if it is not configured, times out or fails, the built-in stub
answers from the route; if nobody can, the student is pointed to the route.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.providers import Assistant, RagAssistant, StubAssistant
from app.assistant.schemas import AnswerSource, AskResponse, RagRequest, RagStep
from app.core.config import Settings, settings
from app.core.exceptions import ApplicationError
from app.regions.catalog import load_regions
from app.routes.service import RouteService
from app.users.models import User
from app.users.repository import UserRepository

logger = logging.getLogger(__name__)


def build_assistants(config: Settings = settings) -> list[Assistant]:
    """The chain of assistants, asked in order until one answers."""
    chain: list[Assistant] = []
    if config.rag_url:
        chain.append(RagAssistant(config.rag_url, config.rag_token, config.rag_timeout_seconds))
    chain.append(StubAssistant())
    return chain


def assistant_mode(config: Settings = settings) -> str:
    """For /health: "rag" when an external service is configured, otherwise "stub"."""
    return "rag" if config.rag_url else "stub"


class AssistantService:
    def __init__(
        self,
        session: AsyncSession,
        lang: str = "ru",
        assistants: list[Assistant] | None = None,
    ) -> None:
        self.session = session
        self.lang = "en" if lang == "en" else "ru"
        self.assistants = assistants if assistants is not None else build_assistants()
        # Step code -> route step id, to turn an answer's step_code into a link.
        self._step_ids: dict[str, UUID] = {}

    async def context(self, user: User, question: str, step_id: UUID | None) -> RagRequest:
        profile = await UserRepository(self.session).get_profile(user.id)
        titles = {region.code: region.title for region in load_regions()}
        request = RagRequest(
            question=question.strip(),
            lang="en" if self.lang == "en" else "ru",
            region_code=profile.region_code if profile else None,
            region_title=titles.get(profile.region_code) if profile else None,
            citizenship=profile.citizenship.value if profile else None,
            university_code=profile.university_code if profile else None,
        )
        routes = RouteService(self.session, self.lang)
        try:
            route = await routes.get_current_model(user)
        except ApplicationError:
            return request
        steps: dict[UUID, RagStep] = {}
        for item in route.steps:
            detail = await routes.get_step(user, route.id, item.id)
            steps[item.id] = RagStep(
                code=detail.code,
                title=detail.title,
                short_description=detail.short_description,
                full_description=detail.full_description,
                location=detail.location,
                sources=[
                    AnswerSource(
                        title=source.title, url=source.url, organization=source.organization
                    )
                    for source in detail.sources
                    if source.source_type != "MOCK"
                ],
            )
        request.route = list(steps.values())
        request.step = steps.get(step_id) if step_id else None
        self._step_ids = {step.code: step_id for step_id, step in steps.items()}
        return request

    async def ask(self, user: User, question: str, step_id: UUID | None = None) -> AskResponse:
        request = await self.context(user, question, step_id)
        fallback = False
        for assistant in self.assistants:
            answer = await assistant.answer(request)
            if answer is None:
                fallback = fallback or assistant.name == "rag"
                continue
            return AskResponse(
                answer=answer.answer,
                sources=[
                    AnswerSource(
                        title=source.title, url=str(source.url), organization=source.organization
                    )
                    for source in answer.sources
                ],
                step_id=self._step_ids.get(answer.step_code or ""),
                provider="rag" if assistant.name == "rag" else "stub",
                fallback=fallback,
            )
        return AskResponse(
            answer=self._no_answer(has_route=bool(request.route)),
            sources=[],
            provider="none",
            fallback=fallback,
        )

    def _no_answer(self, has_route: bool) -> str:
        if not has_route:
            return (
                "Answer a few questions first: I'll build your route and answer about its steps."
                if self.lang == "en"
                else "Сначала ответьте на несколько вопросов: я составлю маршрут и буду отвечать "
                "по его шагам."
            )
        return (
            "I couldn't find this in your route. Open the route: every step links to an "
            "official source, and «Help» has contacts for urgent cases."
            if self.lang == "en"
            else "Не нашёл этого в вашем маршруте. Откройте маршрут: у каждого шага есть "
            "официальный источник, а в разделе «Помощь» — контакты на срочный случай."
        )
