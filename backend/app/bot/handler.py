"""Handles MAX bot updates (webhook or long polling).

The bot is the entry point and notification channel; the Mini App is the main interface,
so the bot greets, shows the next step, lets the user tick a step off right in the chat
and deep-links into the app.
"""

import logging
import re
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApplicationError, InvalidOperationError
from app.notifications.max_sender import parse_step_payload
from app.notifications.service import NotificationService, tr
from app.routes.models import RouteStatus
from app.routes.repository import RouteRepository
from app.routes.service import RouteService
from app.stats.service import StatsService
from app.universities.repository import UniversityRepository
from app.users.repository import UserRepository

logger = logging.getLogger(__name__)

NEXT_COMMANDS = {
    "/next", "следующий шаг", "что дальше", "дальше", "next", "what next", "whats next",
}
START_COMMANDS = {"/start", "начать", "старт"}
GREETINGS = {
    "привет", "приветик", "здравствуйте", "здравствуй", "добрый день", "добрый вечер",
    "доброе утро", "хай", "hi", "hello", "hey",
}
HELP_WORDS = {"help", "помощь", "помоги", "команды"}
THANKS = {"спасибо", "спс", "благодарю", "thanks", "thank you", "thx"}
_PUNCTUATION = re.compile(r"[^\w\s/@]")


def _normalize(text: str) -> str:
    """Lower-case text without punctuation and emoji: «Что дальше?!» -> «что дальше»."""
    return " ".join(_PUNCTUATION.sub(" ", text.lower()).split())


def _user_id(value: Any) -> int | None:
    if isinstance(value, dict):
        raw = value.get("user_id")
        if isinstance(raw, int):
            return raw
    return None


class BotHandler:
    def __init__(
        self,
        notifications: NotificationService,
        session_factory: Callable[[], AsyncSession],
        support_ids: tuple[int, ...] = (),
    ) -> None:
        self.notifications = notifications
        self.session_factory = session_factory
        # Team members: /stats is answered only for them.
        self.support_ids = support_ids

    async def handle(self, update: dict[str, Any]) -> None:
        update_type = update.get("update_type")
        logger.info("MAX update received: %s", update_type)
        if update_type == "bot_started":
            user_id = _user_id(update.get("user"))
            if user_id is not None:
                await self.welcome(user_id, update.get("payload"))
        elif update_type == "message_created":
            await self._on_message(update.get("message") or {})
        elif update_type == "message_callback":
            await self._on_callback(update.get("callback") or {})

    async def _lang(self, max_user_id: int) -> str:
        async with self.session_factory() as session:
            user = await UserRepository(session).get_by_max_user_id(max_user_id)
            return user.lang if user else "ru"

    async def _on_message(self, message: dict[str, Any]) -> None:
        user_id = _user_id(message.get("sender"))
        if user_id is None:
            return
        text = str((message.get("body") or {}).get("text") or "").strip()
        command, _, argument = text.partition(" ")
        command = command.split("@", 1)[0].lower()
        lang = await self._lang(user_id)
        plain = _normalize(text)
        if command in START_COMMANDS or plain in START_COMMANDS:
            await self.welcome(user_id, argument.strip() or None, lang)
        elif command == "/id":
            # For the team: the id to put into SUPPORT_MAX_USER_IDS.
            await self.notifications.send_plain(user_id, f"MAX ID: {user_id}")
        elif command == "/stats" and user_id in self.support_ids:
            await self.notifications.send_plain(user_id, await self._stats_text())
        elif plain in NEXT_COMMANDS or command in NEXT_COMMANDS:
            await self.send_next_step(user_id)
        elif plain in GREETINGS:
            await self.welcome(user_id, None, lang)
        elif plain in THANKS:
            await self.notifications.send_text(
                user_id,
                tr(
                    lang,
                    "Пожалуйста! Когда будете готовы к следующему делу — напишите /next.",
                    "You're welcome! When you're ready for the next task, send /next.",
                ),
                lang,
            )
        elif command.startswith("/") or plain in HELP_WORDS or not plain:
            # /help, an unknown command, an emoji or punctuation: the command list.
            await self.notifications.help(user_id, lang)
        else:
            # A question or any other text: say we don't parse it and point to the route.
            await self.notifications.help(user_id, lang, free_text=True)

    async def _stats_text(self) -> str:
        async with self.session_factory() as session:
            stats = await StatsService(session).collect()
        routes, steps = stats.routes, stats.steps
        median = (
            f"{stats.registration_median_days} дн."
            if stats.registration_median_days is not None
            else "—"
        )
        return (
            "📊 Метрики пилота\n\n"
            f"Пользователей с анкетой: {stats.users}\n"
            f"Маршрутов: {routes.created} (активных {routes.active}, "
            f"завершено {routes.completed}, {round(routes.completion_rate * 100)}%)\n"
            f"Шагов выполнено: {steps.done}, из чата: {steps.done_from_chat}\n"
            f"Напоминаний: {steps.reminders_sent}, после них выполнено: "
            f"{steps.done_after_reminder}\n"
            f"Медиана до регистрации: {median}\n"
            f"Отзывов о шагах: {steps.reported}"
        )

    async def welcome(self, max_user_id: int, payload: object, lang: str = "ru") -> None:
        """Greet the user. A start payload with a university code (``?start=kfu``) adds it."""
        university = None
        if isinstance(payload, str) and payload.strip():
            code = payload.strip().lower().removeprefix("uni_")
            async with self.session_factory() as session:
                university = await UniversityRepository(session).get(code)
        await self.notifications.welcome(
            max_user_id,
            university_code=university.code if university else None,
            university_title=university.short_title if university else None,
            lang=lang,
        )

    async def _on_callback(self, callback: dict[str, Any]) -> None:
        callback_id = callback.get("callback_id")
        user_id = _user_id(callback.get("user"))
        parsed = parse_step_payload(str(callback.get("payload") or ""))
        if not isinstance(callback_id, str) or user_id is None:
            return
        lang = await self._lang(user_id)
        if parsed is None:
            await self.notifications.callback_notice(
                callback_id, tr(lang, "Кнопка устарела", "This button is outdated")
            )
            return
        action, step_id = parsed
        if action in ("snooze", "doing"):
            await self._postpone(callback_id, user_id, step_id, action, lang)
            return

        async with self.session_factory() as session:
            user = await UserRepository(session).get_by_max_user_id(user_id)
            if user is None:
                await self.notifications.callback_notice(
                    callback_id, tr(lang, "Маршрут не найден", "Route not found")
                )
                return
            try:
                title, route = await RouteService(session, lang).complete_from_chat(user, step_id)
            except InvalidOperationError as error:
                notice = (
                    tr(lang, "Этот шаг уже выполнен", "This step is already done")
                    if "already completed" in error.message
                    else tr(
                        lang,
                        "Маршрут обновился — откройте актуальный через /next",
                        "The route has changed — open the current one with /next",
                    )
                )
                await self.notifications.callback_notice(callback_id, notice)
                return
            except ApplicationError:
                await self.notifications.callback_notice(
                    callback_id, tr(lang, "Шаг не найден", "Step not found")
                )
                return

        await self.notifications.callback_done(callback_id, title, lang)
        await self.notifications.step_completed(user_id, route, lang)

    async def _postpone(
        self, callback_id: str, user_id: int, step_id: Any, action: str, lang: str
    ) -> None:
        async with self.session_factory() as session:
            user = await UserRepository(session).get_by_max_user_id(user_id)
            if user is None:
                await self.notifications.callback_notice(
                    callback_id, tr(lang, "Маршрут не найден", "Route not found")
                )
                return
            service = RouteService(session, lang)
            try:
                if action == "snooze":
                    title = await service.snooze_from_chat(user, step_id)
                else:
                    title = await service.start_from_chat(user, step_id)
            except InvalidOperationError:
                await self.notifications.callback_notice(
                    callback_id,
                    tr(
                        lang,
                        "Шаг уже закрыт — откройте актуальный через /next",
                        "This step is closed — open the current one with /next",
                    ),
                )
                return
            except ApplicationError:
                await self.notifications.callback_notice(
                    callback_id, tr(lang, "Шаг не найден", "Step not found")
                )
                return
        if action == "snooze":
            await self.notifications.callback_snoozed(callback_id, title, lang)
        else:
            await self.notifications.callback_started(callback_id, title, lang)

    async def send_next_step(self, max_user_id: int) -> None:
        async with self.session_factory() as session:
            user = await UserRepository(session).get_by_max_user_id(max_user_id)
            lang = user.lang if user else "ru"
            route = await RouteRepository(session).get_current(user.id) if user else None
            if route is None:
                await self.notifications.no_route(max_user_id, lang)
                return
            response = RouteService.route_response(route, lang)
        if response.status == RouteStatus.COMPLETED:
            await self.notifications.route_completed(max_user_id, response, lang)
        else:
            await self.notifications.next_step(max_user_id, response, lang)
