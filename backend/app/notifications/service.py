"""User notifications delivered through the bot.

``NotificationService`` knows *what* to say; a ``MessageSender`` knows *how* to deliver it.
The MAX implementation lives in ``app.notifications.max_sender`` so the texts and triggers
can be tested without MAX.
"""

import logging
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from app.routes.schemas import RouteResponse, RouteStepSummary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutgoingMessage:
    text: str
    button_text: str | None = None
    start_param: str | None = None
    # Adds a "✅ Выполнено" callback button that completes this step from the chat.
    done_step_id: UUID | None = None
    extra_links: list[tuple[str, str]] = field(default_factory=list)


class MessageSender(Protocol):
    async def send(self, max_user_id: int, message: OutgoingMessage) -> bool: ...

    async def acknowledge(
        self, callback_id: str, notification: str, replace_text: str | None = None
    ) -> bool: ...


class NullSender:
    """Used when the bot is not configured: notifications are skipped, not failed."""

    async def send(self, max_user_id: int, message: OutgoingMessage) -> bool:
        logger.info("Bot is not configured, notification skipped")
        return False

    async def acknowledge(
        self, callback_id: str, notification: str, replace_text: str | None = None
    ) -> bool:
        return False


def step_start_param(step_id: UUID) -> str:
    return f"step_{step_id}"


def _progress(route: RouteResponse) -> str:
    return f"Выполнено {route.progress.completed} из {route.progress.total}."


def _next_step(route: RouteResponse) -> RouteStepSummary | None:
    return next((step for step in route.steps if step.id == route.next_step_id), None)


WELCOME_TEXT = (
    "Привет!\n\n"
    "Я помогу разобраться, что нужно сделать после переезда на учёбу.\n\n"
    "Составим персональный маршрут: от документов до доступных студенческих "
    "возможностей.\n\n"
    "Сервис не является государственным и не принимает юридически значимых решений — "
    "у каждого шага указан официальный источник."
)
HELP_TEXT = (
    "Команды:\n"
    "/start — начать и открыть маршрут\n"
    "/next — следующий шаг маршрута\n"
    "Кнопка «✅ Выполнено» под шагом отмечает его прямо в чате\n"
    "/help — эта подсказка"
)


class NotificationService:
    def __init__(self, sender: MessageSender) -> None:
        self.sender = sender

    async def welcome(
        self,
        max_user_id: int,
        university_code: str | None = None,
        university_title: str | None = None,
    ) -> bool:
        text = WELCOME_TEXT
        if university_code and university_title:
            text += (
                f"\n\nВы пришли по приглашению {university_title} — добавим в маршрут "
                "шаги вашего вуза."
            )
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=text,
                button_text="Открыть маршрут",
                start_param=f"uni_{university_code}" if university_code else None,
            ),
        )

    async def help(self, max_user_id: int) -> bool:
        return await self.sender.send(
            max_user_id, OutgoingMessage(text=HELP_TEXT, button_text="Открыть маршрут")
        )

    async def no_route(self, max_user_id: int) -> bool:
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text="Маршрут ещё не составлен. Ответьте на несколько вопросов — это займёт "
                "около минуты.",
                button_text="Составить маршрут",
            ),
        )

    async def route_created(self, max_user_id: int, route: RouteResponse) -> bool:
        step = _next_step(route)
        if step is None:
            return await self.route_completed(max_user_id, route)
        text = (
            f"Ваш маршрут готов: {route.progress.total} шаг(ов).\n\n"
            f"Начните с шага «{step.title}».\n{step.short_description}"
        )
        return await self._send_step(max_user_id, text, step)

    async def next_step(self, max_user_id: int, route: RouteResponse) -> bool:
        step = _next_step(route)
        if step is None:
            return await self.route_completed(max_user_id, route)
        text = (
            f"Следующий шаг в вашем маршруте:\n\n«{step.title}»\n{step.short_description}\n\n"
            f"{_progress(route)}"
        )
        return await self._send_step(max_user_id, text, step)

    async def step_completed(self, max_user_id: int, route: RouteResponse) -> bool:
        if route.next_step_id is None:
            return await self.route_completed(max_user_id, route)
        return await self.next_step(max_user_id, route)

    async def route_completed(self, max_user_id: int, route: RouteResponse) -> bool:
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=(
                    "🎉 Маршрут завершён\n\nВсе необходимые действия из вашего маршрута "
                    f"выполнены. {route.progress.completed} / {route.progress.total}"
                ),
                button_text="Посмотреть маршрут",
            ),
        )

    async def reminder(
        self, max_user_id: int, step_id: UUID, title: str, deadline_text: str | None
    ) -> bool:
        due = f"\nРекомендуемый срок: {deadline_text}." if deadline_text else ""
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=(
                    f"Напоминание\n\nВ вашем маршруте есть следующий шаг:\n\n«{title}»{due}\n\n"
                    "Посмотрите необходимые документы и порядок действий."
                ),
                button_text="Открыть шаг",
                start_param=step_start_param(step_id),
                done_step_id=step_id,
            ),
        )

    async def callback_done(self, callback_id: str, title: str) -> bool:
        """The step was completed from the chat: replace the buttons with a confirmation."""
        return await self.sender.acknowledge(
            callback_id, "Шаг отмечен выполненным", replace_text=f"✅ «{title}» — выполнено"
        )

    async def callback_notice(self, callback_id: str, text: str) -> bool:
        return await self.sender.acknowledge(callback_id, text)

    async def _send_step(self, max_user_id: int, text: str, step: RouteStepSummary) -> bool:
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=text,
                button_text="Открыть шаг",
                start_param=step_start_param(step.id),
                done_step_id=step.id,
            ),
        )
