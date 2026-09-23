"""Handles MAX bot updates (webhook or long polling).

The bot is the entry point and notification channel; the Mini App is the main interface,
so the bot only greets, shows the next step and deep-links into the Mini App.
"""

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.service import NotificationService
from app.routes.models import RouteStatus
from app.routes.repository import RouteRepository
from app.routes.service import RouteService
from app.users.repository import UserRepository

logger = logging.getLogger(__name__)

NEXT_COMMANDS = {"/next", "следующий шаг", "что дальше", "дальше"}
START_COMMANDS = {"/start", "начать", "старт"}
HELP_COMMANDS = {"/help", "помощь"}


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
                await self.notifications.welcome(user_id)
            return

        if update_type != "message_created":
            return
        message = update.get("message") or {}
        user_id = _user_id(message.get("sender"))
        text = str((message.get("body") or {}).get("text") or "").strip().lower()
        if user_id is None:
            return

        command = text.split("@", 1)[0]
        if command in START_COMMANDS:
            await self.notifications.welcome(user_id)
        elif command in NEXT_COMMANDS:
            await self.send_next_step(user_id)
        else:
            await self.notifications.help(user_id)

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
