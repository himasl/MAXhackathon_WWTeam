"""Lifecycle of the bot integration: sender setup, webhook/polling, reminders."""

import asyncio
import contextlib
import logging
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.auth.tokens import issue_link_token
from app.bot.handler import BotHandler
from app.core.config import Settings
from app.core.database import async_session
from app.feedback.models import StepReport
from app.integrations.max.client import MaxApiError, MAXClient
from app.notifications.max_sender import MaxMessageSender
from app.notifications.service import MessageSender, NotificationService, NullSender
from app.regions.catalog import region_timezone
from app.routes.models import RouteStepStatus
from app.routes.repository import RouteRepository
from app.routes.service import localized
from app.sources.models import Source, SourceType
from app.users.models import UserProfile

logger = logging.getLogger(__name__)

UPDATE_TYPES = ["bot_started", "message_created", "message_callback"]
WEBHOOK_PATH = "/max/webhook"
MOSCOW = ZoneInfo("Europe/Moscow")
# Reminders are not sent from 22:00 to 9:00 in the user's region.
QUIET_FROM, QUIET_UNTIL = 22, 9
ALERT_INTERVAL = timedelta(minutes=10)
STALE_SOURCE_DAYS = 90


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
        self.handler = BotHandler(self.notifications, async_session, settings.support_max_user_ids)
        self._tasks: list[asyncio.Task[None]] = []
        self.status = "off"
        self._team_digest_day: date | None = None
        self._last_alert: datetime | None = None

    async def start(self) -> None:
        settings = self.settings
        if not settings.max_bot_token or settings.bot_mode == "off":
            logger.info(
                "MAX bot disabled (BOT_MODE=%s, token %s)",
                settings.bot_mode,
                "set" if settings.max_bot_token else "missing",
            )
            self.status = "off"
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

        key = settings.signing_key

        def link_token(max_user_id: int) -> str | None:
            if not key:
                return None
            return issue_link_token(max_user_id, key, settings.link_token_ttl_seconds)

        self.sender = MaxMessageSender(
            self.client,
            settings.mini_app_url,
            username,
            bot_user_id,
            button_mode=settings.max_button_mode,
            link_token=link_token,
        )
        self.notifications = NotificationService(self.sender)
        self.handler = BotHandler(self.notifications, async_session, settings.support_max_user_ids)

        if settings.bot_mode == "webhook":
            self.status = "webhook" if await self._subscribe_webhook() else "webhook_failed"
        elif settings.bot_mode == "polling":
            self._tasks.append(asyncio.create_task(self._poll(), name="max-polling"))
            self.status = "polling"
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

    async def _subscribe_webhook(self) -> bool:
        assert self.client is not None
        if not self.settings.public_url:
            logger.warning("BOT_MODE=webhook requires PUBLIC_URL, webhook not registered")
            return False
        url = f"{self.settings.public_url}{WEBHOOK_PATH}"
        try:
            await self.client.create_subscription(
                url, UPDATE_TYPES, self.settings.max_webhook_secret or None
            )
            logger.info("MAX webhook registered at %s", url)
            return True
        except Exception as error:  # noqa: BLE001
            logger.warning("MAX webhook registration failed: %s", self._redact(str(error)))
            return False

    def _redact(self, text: str) -> str:
        """MAX may echo request fields in errors; never let secrets reach the logs."""
        for secret in {self.settings.webhook_secret, self.settings.max_webhook_secret}:
            if secret:
                text = text.replace(secret, "***")
        return text

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

    def _is_quiet(self, profile: UserProfile | None, now: datetime) -> bool:
        """22:00–9:00 in the user's region: reminders wait for the morning."""
        hour = now.astimezone(region_timezone(profile.region_code if profile else None)).hour
        return hour >= QUIET_FROM or hour < QUIET_UNTIL

    async def send_due_reminders(self, now: datetime | None = None) -> int:
        """Send one reminder per open step whose recommended deadline is within a day,
        or whose "⏰ tomorrow" has come. Nothing is sent at night in the user's region."""
        current = now or datetime.now(UTC)
        sent = 0
        async with async_session() as session:
            repository = RouteRepository(session)
            due = await repository.list_due_for_reminder(current + timedelta(days=1), current)
            for step in due:
                user = step.route.user
                if self._is_quiet(user.profile, current):
                    continue  # picked up by the first run after the quiet hours
                delivered = await self.notifications.reminder(
                    user.max_user_id,
                    step.id,
                    localized(step.scenario_step, "title", user.lang),
                    format_deadline(step.deadline),
                    user.lang,
                )
                # Mark even when delivery failed so a user who blocked the bot is not spammed.
                step.reminded_at = current
                step.snoozed_until = None
                sent += int(delivered)
            await session.commit()
        return sent

    async def send_weekly_digests(self, now: datetime | None = None) -> int:
        """Sunday 18:00–21:00 local time: what was done this week and what is next."""
        current = now or datetime.now(UTC)
        excluded = set(self.settings.test_access_tokens.values())
        sent = 0
        async with async_session() as session:
            for route in await RouteRepository(session).list_active_with_users():
                user = route.user
                local = current.astimezone(
                    region_timezone(user.profile.region_code if user.profile else None)
                )
                if user.max_user_id in excluded or local.weekday() != 6:
                    continue
                if not 18 <= local.hour < 21:
                    continue
                if user.digest_sent_at and user.digest_sent_at > current - timedelta(days=6):
                    continue
                week_ago = current - timedelta(days=7)
                done = sum(
                    1
                    for step in route.steps
                    if step.status == RouteStepStatus.DONE
                    and step.completed_at is not None
                    and step.completed_at >= week_ago
                )
                open_steps = [
                    step
                    for step in route.steps
                    if step.status in (RouteStepStatus.TODO, RouteStepStatus.IN_PROGRESS)
                ]
                next_title = (
                    localized(open_steps[0].scenario_step, "title", user.lang)
                    if open_steps
                    else None
                )
                sent += int(
                    await self.notifications.weekly_digest(
                        user.max_user_id, done, len(open_steps), next_title, user.lang
                    )
                )
                user.digest_sent_at = current
            await session.commit()
        return sent

    async def send_team_digest(self, now: datetime | None = None, force: bool = False) -> int:
        """Once a day at 10:00 Moscow time: new «Сообщить о неточности» notes; on Mondays
        also sources checked more than 90 days ago. Sent to SUPPORT_MAX_USER_IDS."""
        support = self.settings.support_max_user_ids
        current = now or datetime.now(UTC)
        local = current.astimezone(MOSCOW)
        if not support or (
            not force and (local.hour != 10 or self._team_digest_day == local.date())
        ):
            return 0
        self._team_digest_day = local.date()
        parts: list[str] = []
        async with async_session() as session:
            reports = list(
                await session.scalars(
                    select(StepReport)
                    .where(StepReport.notified_at.is_(None))
                    .order_by(StepReport.created_at)
                    .limit(50)
                )
            )
            if reports:
                parts.append(f"📝 Отзывы о шагах за сутки: {len(reports)}")
                parts.extend(
                    f"\n{index}. {report.summary}" for index, report in enumerate(reports, 1)
                )
            for report in reports:
                report.notified_at = current
            if local.weekday() == 0:
                stale = list(
                    await session.scalars(
                        select(Source)
                        .where(
                            Source.source_type == SourceType.OFFICIAL,
                            Source.checked_at < current - timedelta(days=STALE_SOURCE_DAYS),
                        )
                        .order_by(Source.checked_at)
                        .limit(30)
                    )
                )
                if stale:
                    parts.append(
                        f"\n🕰 Источники, проверенные больше {STALE_SOURCE_DAYS} дней назад: "
                        f"{len(stale)}. Проверьте ссылки (tools/check_sources.py) и обновите "
                        "checked_at:"
                    )
                    parts.extend(f"• {source.title} — {source.url}" for source in stale)
            await session.commit()
        if not parts:
            return 0
        text = "\n".join(parts)
        return sum([int(await self.notifications.send_plain(member, text)) for member in support])

    async def alert_team(self, text: str, now: datetime | None = None) -> bool:
        """A server error: tell the team at most once in ALERT_INTERVAL."""
        current = now or datetime.now(UTC)
        support = self.settings.support_max_user_ids
        if not support or (self._last_alert and current - self._last_alert < ALERT_INTERVAL):
            return False
        self._last_alert = current
        for member in support:
            await self.notifications.send_plain(member, text)
        return True

    async def _reminders(self) -> None:
        while True:
            try:
                await self.send_due_reminders()
                await self.send_weekly_digests()
                await self.send_team_digest()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Reminder run failed")
            await asyncio.sleep(max(60, self.settings.reminder_interval_seconds))
