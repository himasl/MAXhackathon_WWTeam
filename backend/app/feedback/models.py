from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPrimaryKeyMixin


class ReportKind(StrEnum):
    OUTDATED = "OUTDATED"  # the source or the conditions have changed
    NOT_APPLICABLE = "NOT_APPLICABLE"  # the step does not fit the user's situation
    OTHER = "OTHER"


class StepReport(UUIDPrimaryKeyMixin, Base):
    """A user's note that a step is outdated or wrong: the team's data-quality feedback."""

    __tablename__ = "step_reports"

    route_step_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_route_steps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[ReportKind] = mapped_column(Enum(ReportKind, name="report_kind"), nullable=False)
    comment: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
