import logging
from typing import Any
from urllib.parse import quote

from app.integrations.max.client import MaxApiError, MAXClient
from app.integrations.max.keyboards import keyboard, link_button, open_app_button
from app.notifications.service import OutgoingMessage

logger = logging.getLogger(__name__)


class MaxMessageSender:
    """Delivers messages via the MAX Bot API with a button that opens the Mini App.

    ``open_app`` is preferred. If MAX rejects it (for example the Mini App is not yet
    attached to the bot), the message is resent with a plain link button so the user still
    gets the notification.
    """

    def __init__(
        self,
        client: MAXClient,
        mini_app_url: str,
        bot_username: str = "",
        bot_user_id: int | None = None,
    ) -> None:
        self.client = client
        self.mini_app_url = mini_app_url
        self.bot_username = bot_username
        self.bot_user_id = bot_user_id
        self._open_app_supported = bool(bot_username or bot_user_id)

    def _deep_link(self, start_param: str | None) -> str:
        if self.bot_username:
            base = f"https://max.ru/{self.bot_username}"
            return f"{base}?startapp={quote(start_param)}" if start_param else base
        if start_param:
            return f"{self.mini_app_url}/#/start/{quote(start_param)}"
        return self.mini_app_url

    def _attachments(self, message: OutgoingMessage, use_open_app: bool) -> list[dict[str, Any]]:
        rows: list[list[dict[str, Any]]] = []
        if message.button_text:
            if use_open_app:
                rows.append(
                    [
                        open_app_button(
                            message.button_text,
                            self.bot_username or str(self.bot_user_id),
                            self.bot_user_id,
                            message.start_param,
                        )
                    ]
                )
            else:
                rows.append([link_button(message.button_text, self._deep_link(message.start_param))])
        rows.extend([link_button(text, url)] for text, url in message.extra_links)
        return [keyboard(*rows)] if rows else []

    async def _deliver(self, max_user_id: int, message: OutgoingMessage, open_app: bool) -> None:
        await self.client.send_message(
            message.text,
            user_id=max_user_id,
            attachments=self._attachments(message, open_app),
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
