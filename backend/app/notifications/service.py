"""User notifications delivered through the bot.

``NotificationService`` knows *what* to say; a ``MessageSender`` knows *how* to deliver it.
The MAX implementation lives in ``app.notifications.max_sender`` so the texts and triggers
can be tested without MAX. Every text exists in Russian and English: the language is the one
the user chose in the app (``User.lang``).
"""

import logging
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from app.assistant.schemas import AskResponse
from app.routes.schemas import RouteResponse, RouteStepSummary

logger = logging.getLogger(__name__)


def tr(lang: str, ru: str, en: str) -> str:
    return en if lang == "en" else ru


@dataclass(frozen=True)
class OutgoingMessage:
    text: str
    button_text: str | None = None
    start_param: str | None = None
    # Adds a "✅ Выполнено" callback button that completes this step from the chat.
    done_step_id: UUID | None = None
    # With done_step_id: adds "⏰ Напомнить завтра" and "🚶 Уже в процессе" buttons.
    snooze: bool = False
    extra_links: list[tuple[str, str]] = field(default_factory=list)
    lang: str = "ru"


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


def _progress(route: RouteResponse, lang: str) -> str:
    done, total = route.progress.completed, route.progress.total
    return tr(lang, f"Выполнено {done} из {total}.", f"Done: {done} of {total}.")


def _next_step(route: RouteResponse) -> RouteStepSummary | None:
    return next((step for step in route.steps if step.id == route.next_step_id), None)


WELCOME_TEXT = {
    "ru": (
        "Привет!\n\n"
        "Я помогу разобраться, что нужно сделать после переезда на учёбу.\n\n"
        "Составим персональный маршрут: от документов до доступных студенческих "
        "возможностей.\n\n"
        "Сервис не является государственным и не принимает юридически значимых решений — "
        "у каждого шага указан официальный источник."
    ),
    "en": (
        "Hi!\n\n"
        "I'll help you sort out what to do after moving to study.\n\n"
        "We'll build a personal route: from documents to student benefits.\n\n"
        "This is not a government service and makes no legal decisions — every step links "
        "to an official source."
    ),
}
HELP_TEXT = {
    "ru": (
        "Команды:\n"
        "/start — начать и открыть маршрут\n"
        "/next — следующий шаг маршрута\n"
        "/help — эта подсказка\n\n"
        "Под напоминанием: «✅ Выполнено» отмечает шаг, «⏰ Напомнить завтра» переносит "
        "напоминание, «🚶 Уже в процессе» — отмечает, что дело начато."
    ),
    "en": (
        "Commands:\n"
        "/start — start and open the route\n"
        "/next — the next step\n"
        "/help — this help\n\n"
        "Under a reminder: “✅ Done” completes the step, “⏰ Remind tomorrow” postpones it, "
        "“🚶 Already on it” marks it as started."
    ),
}


class NotificationService:
    def __init__(self, sender: MessageSender) -> None:
        self.sender = sender

    async def welcome(
        self,
        max_user_id: int,
        university_code: str | None = None,
        university_title: str | None = None,
        lang: str = "ru",
    ) -> bool:
        text = WELCOME_TEXT[tr(lang, "ru", "en")]
        if university_code and university_title:
            text += tr(
                lang,
                f"\n\nВы пришли по приглашению {university_title} — добавим в маршрут "
                "шаги вашего вуза.",
                f"\n\nYou were invited by {university_title} — we'll add your university's steps.",
            )
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=text,
                button_text=tr(lang, "Открыть маршрут", "Open the route"),
                start_param=f"uni_{university_code}" if university_code else None,
                lang=lang,
            ),
        )

    async def help(self, max_user_id: int, lang: str = "ru", free_text: bool = False) -> bool:
        text = HELP_TEXT[tr(lang, "ru", "en")]
        if free_text:
            # A question or any other text the bot does not parse: point to the route.
            text = (
                tr(
                    lang,
                    "Вопросы текстом я пока не разбираю. Ответ, скорее всего, уже есть "
                    "в шагах вашего маршрута — откройте его кнопкой ниже или напишите /next.",
                    "I can't read free-text questions yet. The answer is most likely in the "
                    "steps of your route — open it with the button below or send /next.",
                )
                + "\n\n"
                + text
            )
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=text,
                button_text=tr(lang, "Открыть маршрут", "Open the route"),
                lang=lang,
            ),
        )

    async def answer(self, max_user_id: int, answer: AskResponse, lang: str = "ru") -> bool:
        """The assistant's answer to a free-text question, with official sources as links."""
        note = tr(
            lang,
            "\n\nОтвет может быть неточным — проверяйте по официальному источнику.",
            "\n\nThe answer may be inaccurate — check the official source.",
        )
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=answer.answer + (note if answer.sources else ""),
                button_text=tr(lang, "Открыть шаг", "Open the step")
                if answer.step_id
                else tr(lang, "Открыть маршрут", "Open the route"),
                start_param=step_start_param(answer.step_id) if answer.step_id else None,
                extra_links=[(source.title[:60], source.url) for source in answer.sources[:3]],
                lang=lang,
            ),
        )

    async def admin_panel(self, max_user_id: int) -> bool:
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text="Панель команды: статистика, ссылки по регионам и отзывы пользователей.",
                button_text="Открыть панель",
                start_param="admin",
            ),
        )

    async def no_route(self, max_user_id: int, lang: str = "ru") -> bool:
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=tr(
                    lang,
                    "Маршрут ещё не составлен. Ответьте на несколько вопросов — это займёт "
                    "около минуты.",
                    "Your route is not built yet. Answer a few questions — it takes about a "
                    "minute.",
                ),
                button_text=tr(lang, "Составить маршрут", "Build my route"),
                lang=lang,
            ),
        )

    async def route_created(self, max_user_id: int, route: RouteResponse, lang: str = "ru") -> bool:
        step = _next_step(route)
        if step is None:
            return await self.route_completed(max_user_id, route, lang)
        total = route.progress.total
        text = tr(
            lang,
            f"Ваш маршрут готов: {total} шаг(ов).\n\n"
            f"Начните с шага «{step.title}».\n{step.short_description}",
            f"Your route is ready: {total} step(s).\n\n"
            f"Start with “{step.title}”.\n{step.short_description}",
        )
        return await self._send_step(max_user_id, text, step, lang)

    async def next_step(self, max_user_id: int, route: RouteResponse, lang: str = "ru") -> bool:
        step = _next_step(route)
        if step is None:
            return await self.route_completed(max_user_id, route, lang)
        text = tr(
            lang,
            f"Следующий шаг в вашем маршруте:\n\n«{step.title}»\n{step.short_description}",
            f"The next step in your route:\n\n“{step.title}”\n{step.short_description}",
        )
        return await self._send_step(max_user_id, f"{text}\n\n{_progress(route, lang)}", step, lang)

    async def step_completed(
        self, max_user_id: int, route: RouteResponse, lang: str = "ru"
    ) -> bool:
        if route.next_step_id is None:
            return await self.route_completed(max_user_id, route, lang)
        return await self.next_step(max_user_id, route, lang)

    async def route_completed(
        self, max_user_id: int, route: RouteResponse, lang: str = "ru"
    ) -> bool:
        done, total = route.progress.completed, route.progress.total
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=tr(
                    lang,
                    "🎉 Маршрут завершён\n\nВсе необходимые действия из вашего маршрута "
                    f"выполнены. {done} / {total}",
                    f"🎉 Route completed\n\nEverything in your route is done. {done} / {total}",
                ),
                button_text=tr(lang, "Посмотреть маршрут", "View the route"),
                lang=lang,
            ),
        )

    async def reminder(
        self,
        max_user_id: int,
        step_id: UUID,
        title: str,
        deadline_text: str | None,
        lang: str = "ru",
    ) -> bool:
        due = (
            tr(
                lang,
                f"\nРекомендуемый срок: {deadline_text}.",
                f"\nRecommended by {deadline_text}.",
            )
            if deadline_text
            else ""
        )
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=tr(
                    lang,
                    f"Напоминание\n\nВ вашем маршруте есть следующий шаг:\n\n«{title}»{due}\n\n"
                    "Посмотрите необходимые документы и порядок действий.",
                    f"Reminder\n\nThe next step in your route:\n\n“{title}”{due}\n\n"
                    "Check the documents you need and what to do.",
                ),
                button_text=tr(lang, "Открыть шаг", "Open the step"),
                start_param=step_start_param(step_id),
                done_step_id=step_id,
                snooze=True,
                lang=lang,
            ),
        )

    async def weekly_digest(
        self,
        max_user_id: int,
        done_this_week: int,
        left: int,
        next_title: str | None,
        lang: str = "ru",
    ) -> bool:
        """Sunday summary: what was done this week and what comes next."""
        if done_this_week:
            head = tr(
                lang,
                f"За неделю сделано дел: {done_this_week}. Так держать!",
                f"Done this week: {done_this_week}. Keep it up!",
            )
        else:
            head = tr(
                lang,
                "На этой неделе дел в маршруте не закрыто — ничего страшного.",
                "No steps closed this week — that's okay.",
            )
        rest = tr(lang, f"Осталось: {left}.", f"Left: {left}.")
        following = (
            tr(lang, f"\nСледующее: «{next_title}».", f"\nNext: “{next_title}”.")
            if next_title
            else ""
        )
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=tr(lang, "Итоги недели\n\n", "Your week\n\n") + f"{head}\n{rest}{following}",
                button_text=tr(lang, "Открыть маршрут", "Open the route"),
                lang=lang,
            ),
        )

    async def send_text(self, max_user_id: int, text: str, lang: str = "ru") -> bool:
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=text, button_text=tr(lang, "Открыть маршрут", "Open the route"), lang=lang
            ),
        )

    async def send_plain(self, max_user_id: int, text: str) -> bool:
        """A message without buttons: team alerts and digests."""
        return await self.sender.send(max_user_id, OutgoingMessage(text=text))

    async def callback_snoozed(self, callback_id: str, title: str, lang: str = "ru") -> bool:
        return await self.sender.acknowledge(
            callback_id,
            tr(lang, "Напомню завтра", "I'll remind you tomorrow"),
            replace_text=tr(
                lang,
                f"⏰ Напомню завтра о шаге «{title}»",
                f"⏰ I'll remind you about “{title}” tomorrow",
            ),
        )

    async def callback_started(self, callback_id: str, title: str, lang: str = "ru") -> bool:
        return await self.sender.acknowledge(
            callback_id,
            tr(lang, "Отметил: в процессе", "Marked as in progress"),
            replace_text=tr(
                lang,
                f"🚶 «{title}» — в процессе. Загляну через 3 дня; отметить выполненным "
                "можно в маршруте или командой /next.",
                f"🚶 “{title}” is in progress. I'll check back in 3 days; mark it as done in "
                "the route or with /next.",
            ),
        )

    async def callback_done(self, callback_id: str, title: str, lang: str = "ru") -> bool:
        """The step was completed from the chat: replace the buttons with a confirmation."""
        return await self.sender.acknowledge(
            callback_id,
            tr(lang, "Шаг отмечен выполненным", "Step marked as done"),
            replace_text=tr(lang, f"✅ «{title}» — выполнено", f"✅ “{title}” — done"),
        )

    async def callback_notice(self, callback_id: str, text: str) -> bool:
        return await self.sender.acknowledge(callback_id, text)

    async def _send_step(
        self, max_user_id: int, text: str, step: RouteStepSummary, lang: str = "ru"
    ) -> bool:
        return await self.sender.send(
            max_user_id,
            OutgoingMessage(
                text=text,
                button_text=tr(lang, "Открыть шаг", "Open the step"),
                start_param=step_start_param(step.id),
                done_step_id=step.id,
                lang=lang,
            ),
        )
