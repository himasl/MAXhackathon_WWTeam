from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserActivity(Base):
    """One row per user, day (Moscow time) and channel ("app" or "bot") with any activity.

    Enough for daily/weekly/monthly active users and returning users, without storing
    what exactly the user did."""

    __tablename__ = "user_activity"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    channel: Mapped[str] = mapped_column(String(8), primary_key=True)
