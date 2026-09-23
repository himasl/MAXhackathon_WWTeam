"""Minimal RFC 5545 calendar file for a step's recommended deadline."""

from datetime import UTC, date, datetime, timedelta


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold lines longer than 75 octets (CRLF + space), never splitting a UTF-8 char."""
    if len(line.encode()) <= 75:
        return line
    parts: list[str] = []
    current = ""
    for char in line:
        if len((current + char).encode()) > 74:
            parts.append(current)
            current = ""
        current += char
    parts.append(current)
    return "\r\n ".join(parts)


def step_event(
    uid: str,
    title: str,
    description: str,
    day: date,
    url: str,
    now: datetime | None = None,
) -> str:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Marshrut//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}@marshrut",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
        f"SUMMARY:{_escape('Маршрут: ' + title)}",
        f"DESCRIPTION:{_escape(description)}",
        f"URL:{url}",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_escape(title)}",
        "TRIGGER:-P1D",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
