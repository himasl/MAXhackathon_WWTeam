import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from app.integrations.max.client import MaxApiError, MAXClient
from app.integrations.max.keyboards import (
    callback_button,
    keyboard,
    link_button,
    open_app_button,
)
from app.notifications.service import OutgoingMessage

logger = logging.getLogger(__name__)

type LinkTokenFactory = Callable[[int], str | None]

DONE_PREFIX = "done:"
# Callback actions on a step: done, remind tomorrow, already in progress.
STEP_ACTIONS = ("done", "snooze", "doing")


def done_payload(step_id: UUID) -> str:
    return f"{DONE_PREFIX}{step_id}"


def step_payload(action: str, step_id: UUID) -> str:
    return f"{action}:{step_id}"


def parse_step_payload(payload: str) -> tuple[str, UUID] | None:
    action, _, raw = payload.partition(":")
    if action not in STEP_ACTIONS:
        return None
    try:
        return action, UUID(raw)
    except ValueError:
        return None


def parse_done_payload(payload: str) -> UUID | None:
    parsed = parse_step_payload(payload)
    return parsed[1] if parsed and parsed[0] == "done" else None


class MaxMessageSender:
    """Delivers messages via the MAX Bot API with a button that opens the app.

    ``button_mode="open_app"`` uses the Mini App registered for the bot. If MAX rejects the
    button, the message is resent with a link button. ``button_mode="link"`` always sends a
    link to the web app with a signed per-user token, so the user is signed in even when
    the Mini App URL is not configured on the MAX platform.
    """

    def __init__(
        self,
        client: MAXClient,
        mini_app_url: str,
        bot_username: str = "",
        bot_user_id: int | None = None,
        button_mode: str = "link",
        link_token: LinkTokenFactory | None = None,
    ) -> None:
        self.client = client
        self.mini_app_url = mini_app_url.rstrip("/")
        self.bot_username = bot_username
        self.bot_user_id = bot_user_id
        self.link_token = link_token
        self._open_app_supported = button_mode == "open_app" and bool(
            bot_username or bot_user_id
        )

    def app_link(self, max_user_id: int, start_param: str | None) -> str:
        params: dict[str, str] = {}
        token = self.link_token(max_user_id) if self.link_token else None
        if token:
            params["t"] = token
        if start_param:
            params["start"] = start_param
        return f"{self.mini_app_url}/?{urlencode(params)}" if params else f"{self.mini_app_url}/"

    def _attachments(
        self, max_user_id: int, message: OutgoingMessage, use_open_app: bool
    ) -> list[dict[str, Any]]:
        rows: list[list[dict[str, Any]]] = []
        if message.button_text:
            if use_open_app:
                button = open_app_button(
                    message.button_text,
                    self.bot_username or str(self.bot_user_id),
                    self.bot_user_id,
                    message.start_param,
                )
            else:
                button = link_button(
                    message.button_text, self.app_link(max_user_id, message.start_param)
                )
            rows.append([button])
        if message.done_step_id is not None:
            rows.append([callback_button("✅ Выполнено", done_payload(message.done_step_id))])
            if message.snooze:
                rows.append(
                    [
                        callback_button(
                            "⏰ Напомнить завтра", step_payload("snooze", message.done_step_id)
                        ),
                        callback_button(
                            "🚶 Уже в процессе", step_payload("doing", message.done_step_id)
                        ),
                    ]
                )
        rows.extend([link_button(text, url)] for text, url in message.extra_links)
        return [keyboard(*rows)] if rows else []

    async def _deliver(self, max_user_id: int, message: OutgoingMessage, open_app: bool) -> None:
        await self.client.send_message(
            message.text,
            user_id=max_user_id,
            attachments=self._attachments(max_user_id, message, open_app),
        )

    async def send(self, max_user_id: int, message: OutgoingMessage) -> bool:
        use_open_app = self._open_app_supported and bool(message.button_text)
        try:
            try:
                await self._deliver(max_user_id, message, use_open_app)
            except MaxApiError as error:
                if not (use_open_app and error.status_code == 400):
                    raise
                logger.warning("open_app button rejected by MAX, retrying with a link button")
                await self._deliver(max_user_id, message, open_app=False)
                # The link version went through, so the open_app button is the problem.
                self._open_app_supported = False
            return True
        except MaxApiError as error:
            logger.warning("MAX message was not delivered: %s", error)
        except Exception:
            logger.exception("MAX message was not delivered")
        return False

    async def acknowledge(
        self, callback_id: str, notification: str, replace_text: str | None = None
    ) -> bool:
        message = None if replace_text is None else {"text": replace_text, "attachments": []}
        try:
            await self.client.answer_callback(
                callback_id, notification=notification, message=message
            )
            return True
        except Exception as error:  # noqa: BLE001
            logger.warning("MAX callback answer failed: %s", error)
            return False
