from typing import Any

type Button = dict[str, Any]


def keyboard(*rows: list[Button]) -> dict[str, Any]:
    return {"type": "inline_keyboard", "payload": {"buttons": [row for row in rows if row]}}


def open_app_button(
    text: str, web_app: str, contact_id: int | None, payload: str | None = None
) -> Button:
    button: Button = {"type": "open_app", "text": text, "web_app": web_app}
    if contact_id is not None:
        button["contact_id"] = contact_id
    if payload:
        button["payload"] = payload
    return button


def link_button(text: str, url: str) -> Button:
    return {"type": "link", "text": text, "url": url}

