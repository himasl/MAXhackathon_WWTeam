"""Handles MAX bot updates (webhook or long polling).

The bot is the entry point and notification channel; the Mini App is the main interface,
so the bot greets, shows the next step, lets the user tick a step off right in the chat
and deep-links into the app.
"""

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApplicationError, InvalidOperationError
from app.notifications.max_sender import parse_step_payload
from app.notifications.service import NotificationService
from app.routes.models import RouteStatus
from app.routes.repository import RouteRepository
from app.routes.service import RouteService
from app.universities.repository import UniversityRepository
from app.users.repository import UserRepository

logger = logging.getLogger(__name__)

NEXT_COMMANDS = {"/next", "следующий шаг", "что дальше", "дальше"}
START_COMMANDS = {"/start", "начать", "старт"}


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
    ) -> None:
        self.notifications = notifications
        self.session_factory = session_factory

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

    async def _on_message(self, message: dict[str, Any]) -> None:
        user_id = _user_id(message.get("sender"))
        if user_id is None:
            return
        text = str((message.get("body") or {}).get("text") or "").strip()
        command, _, argument = text.partition(" ")
        command = command.split("@", 1)[0].lower()
        if command in START_COMMANDS:
            await self.welcome(user_id, argument.strip() or None)
        elif text.lower() in NEXT_COMMANDS or command in NEXT_COMMANDS:
            await self.send_next_step(user_id)
        else:
            # /help and any other text: answer with the command list.
            await self.notifications.help(user_id)

    async def welcome(self, max_user_id: int, payload: object) -> None:
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
        )

    async def _on_callback(self, callback: dict[str, Any]) -> None:
        callback_id = callback.get("callback_id")
        user_id = _user_id(callback.get("user"))
        parsed = parse_step_payload(str(callback.get("payload") or ""))
        if not isinstance(callback_id, str) or user_id is None:
            return
        if parsed is None:
            await self.notifications.callback_notice(callback_id, "Кнопка устарела")
            return
        action, step_id = parsed
        if action in ("snooze", "doing"):
            await self._postpone(callback_id, user_id, step_id, action)
            return

        async with self.session_factory() as session:
            user = await UserRepository(session).get_by_max_user_id(user_id)
            if user is None:
                await self.notifications.callback_notice(callback_id, "Маршрут не найден")
                return
            try:
                title, route = await RouteService(session).complete_from_chat(user, step_id)
            except InvalidOperationError as error:
                notice = (
                    "Этот шаг уже выполнен"
                    if "already completed" in error.message
                    else "Маршрут обновился — откройте актуальный через /next"
                )
                await self.notifications.callback_notice(callback_id, notice)
                return
            except ApplicationError:
                await self.notifications.callback_notice(callback_id, "Шаг не найден")
                return

        await self.notifications.callback_done(callback_id, title)
        await self.notifications.step_completed(user_id, route)

    async def _postpone(self, callback_id: str, user_id: int, step_id: Any, action: str) -> None:
        async with self.session_factory() as session:
            user = await UserRepository(session).get_by_max_user_id(user_id)
            if user is None:
                await self.notifications.callback_notice(callback_id, "Маршрут не найден")
                return
            service = RouteService(session)
            try:
                if action == "snooze":
                    title = await service.snooze_from_chat(user, step_id)
                else:
                    title = await service.start_from_chat(user, step_id)
            except InvalidOperationError:
                await self.notifications.callback_notice(
                    callback_id, "Шаг уже закрыт — откройте актуальный через /next"
                )
                return
            except ApplicationError:
                await self.notifications.callback_notice(callback_id, "Шаг не найден")
                return
        if action == "snooze":
            await self.notifications.callback_snoozed(callback_id, title)
        else:
            await self.notifications.callback_started(callback_id, title)

    async def send_next_step(self, max_user_id: int) -> None:
        async with self.session_factory() as session:
            user = await UserRepository(session).get_by_max_user_id(max_user_id)
            route = await RouteRepository(session).get_current(user.id) if user else None
            if route is None:
                await self.notifications.no_route(max_user_id)
                return
            response = RouteService.route_response(route)
        if response.status == RouteStatus.COMPLETED:
            await self.notifications.route_completed(max_user_id, response)
        else:
            await self.notifications.next_step(max_user_id, response)
