"""Records that a user was active today in the app or the bot (for the team panel)."""

import logging
from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert

from app.admin.models import UserActivity
from app.core.database import async_session

logger = logging.getLogger(__name__)
MOSCOW = ZoneInfo("Europe/Moscow")
# (user, day, channel) already written by this process: one insert per user per day.
_seen: set[tuple[UUID, date, str]] = set()


def today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(MOSCOW).date()


async def record_activity(user_id: UUID, channel: str) -> None:
    key = (user_id, today(), channel)
    if key in _seen:
        return
    try:
        async with async_session() as session:
            await session.execute(
                insert(UserActivity)
                .values(user_id=user_id, day=key[1], channel=channel)
                .on_conflict_do_nothing()
            )
            await session.commit()
    except Exception:
        logger.warning("Could not record activity", exc_info=True)
        return
    if len(_seen) > 50_000:
        _seen.clear()
    _seen.add(key)
