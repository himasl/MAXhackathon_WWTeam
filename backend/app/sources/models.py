from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Table, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.scenarios.models import ScenarioStep


class SourceType(StrEnum):
    OFFICIAL = "OFFICIAL"
    MOCK = "MOCK"
    OTHER = "OTHER"


scenario_step_sources = Table(
    "scenario_step_sources",
    Base.metadata,
    Column(
        "scenario_step_id",
        Uuid,
        ForeignKey("scenario_steps.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "source_id",
        Uuid,
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Source(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sources"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    organization: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type"), nullable=False
    )
    region_code: Mapped[str | None] = mapped_column(String(32))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scenario_steps: Mapped[list[ScenarioStep]] = relationship(
        secondary=scenario_step_sources, back_populates="sources"
    )
