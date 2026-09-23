"""Lifecycle of the bot integration: sender setup, webhook/polling, reminders."""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.bot.handler import BotHandler
from app.core.config import Settings
from app.core.database import async_session
from app.integrations.max.client import MaxApiError, MAXClient
from app.notifications.max_sender import MaxMessageSender
from app.notifications.service import MessageSender, NotificationService, NullSender
from app.routes.repository import RouteRepository

logger = logging.getLogger(__name__)

UPDATE_TYPES = ["bot_started", "message_created"]
WEBHOOK_PATH = "/max/webhook"
MOSCOW = ZoneInfo("Europe/Moscow")


def format_deadline(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(MOSCOW).strftime("%d.%m.%Y")


class BotRuntime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: MAXClient | None = None
        self.sender: MessageSender = NullSender()
        self.notifications = NotificationService(self.sender)
        self.handler = BotHandler(self.notifications, async_session)
        self._tasks: list[asyncio.Task[None]] = []

    @property
    def enabled(self) -> bool:
        return self.client is not None

    async def start(self) -> None:
        settings = self.settings
        if not settings.max_bot_token or settings.bot_mode == "off":
            logger.info("MAX bot disabled (BOT_MODE=%s)", settings.bot_mode)
            return

        self.client = MAXClient(
            settings.max_bot_token, settings.max_api_url, ca_bundle=settings.max_ca_bundle
        )
        username, bot_user_id = settings.max_bot_username, None
        try:
            me = await self.client.get_me()
            username = username or str(me.get("username") or "")
            raw_id = me.get("user_id")
            bot_user_id = raw_id if isinstance(raw_id, int) else None
            logger.info("MAX bot connected as @%s", username or bot_user_id)
        except Exception as error:  # noqa: BLE001 - the API must start even if MAX is down
            logger.warning("MAX /me failed, continuing without bot identity: %s", error)

        self.sender = MaxMessageSender(
            self.client, settings.mini_app_url, username, bot_user_id
        )
        self.notifications = NotificationService(self.sender)
        self.handler = BotHandler(self.notifications, async_session)

        if settings.bot_mode == "webhook":
            await self._subscribe_webhook()
        elif settings.bot_mode == "polling":
            self._tasks.append(asyncio.create_task(self._poll(), name="max-polling"))
        if settings.reminders_enabled:
            self._tasks.append(asyncio.create_task(self._reminders(), name="reminders"))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()
        if self.client is not None:
            await self.client.close()

    async def _subscribe_webhook(self) -> None:
        assert self.client is not None
        if not self.settings.public_url:
            logger.warning("BOT_MODE=webhook requires PUBLIC_URL, webhook not registered")
            return
        url = f"{self.settings.public_url}{WEBHOOK_PATH}"
        try:
            await self.client.create_subscription(
                url, UPDATE_TYPES, self.settings.webhook_secret or None
            )
            logger.info("MAX webhook registered at %s", url)
        except Exception as error:  # noqa: BLE001
            logger.warning("MAX webhook registration failed: %s", error)

    async def _poll(self) -> None:
        assert self.client is not None
        marker: int | None = None
        while True:
            try:
                data = await self.client.get_updates(marker, timeout=30, types=UPDATE_TYPES)
                marker = data.get("marker", marker)
                for update in data.get("updates", []):
                    await self.safe_handle(update)
            except asyncio.CancelledError:
                raise
            except MaxApiError as error:
                logger.warning("MAX polling error: %s", error)
                await asyncio.sleep(5)
            except Exception:
                logger.exception("MAX polling failed")
                await asyncio.sleep(5)

    async def safe_handle(self, update: dict[str, object]) -> None:
        try:
            await self.handler.handle(update)
        except Exception:
            logger.exception("Bot update handling failed")

    async def send_due_reminders(self, now: datetime | None = None) -> int:
        """Send one reminder per open step whose recommended deadline is within a day."""
        current = now or datetime.now(UTC)
        sent = 0
        async with async_session() as session:
            repository = RouteRepository(session)
            for step in await repository.list_due_for_reminder(current + timedelta(days=1)):
                delivered = await self.notifications.reminder(
                    step.route.user.max_user_id,
                    step.id,
                    step.scenario_step.title,
                    format_deadline(step.deadline),
                )
                # Mark even when delivery failed so a user who blocked the bot is not spammed.
                step.reminded_at = current
                sent += int(delivered)
            await session.commit()
        return sent

    async def _reminders(self) -> None:
        while True:
            try:
                await self.send_due_reminders()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Reminder run failed")
            await asyncio.sleep(max(60, self.settings.reminder_interval_seconds))
