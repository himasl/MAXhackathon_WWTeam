from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.sources.models import scenario_step_sources

if TYPE_CHECKING:
    from app.documents.models import ScenarioStepDocument
    from app.routes.models import UserRouteStep
    from app.sources.models import Source


class StepCategory(StrEnum):
    REGISTRATION = "REGISTRATION"
    HEALTHCARE = "HEALTHCARE"
    EDUCATION = "EDUCATION"
    TRANSPORT = "TRANSPORT"
    SOCIAL_SUPPORT = "SOCIAL_SUPPORT"
    OTHER = "OTHER"


class RuleOperator(StrEnum):
    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    IN = "IN"
    NOT_IN = "NOT_IN"


class Scenario(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scenarios"
    __table_args__ = (UniqueConstraint("code", "version"),)

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    steps: Mapped[list[ScenarioStep]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan", order_by="ScenarioStep.position"
    )


class ScenarioStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scenario_steps"
    __table_args__ = (
        CheckConstraint("estimated_duration >= 0", name="estimated_duration_non_negative"),
        CheckConstraint("recommended_days >= 0", name="recommended_days_non_negative"),
        UniqueConstraint("scenario_id", "code"),
    )

    scenario_id: Mapped[UUID] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_description: Mapped[str] = mapped_column(Text, nullable=False)
    full_description: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[StepCategory] = mapped_column(
        Enum(StepCategory, name="step_category"), nullable=False
    )
    estimated_duration: Mapped[int | None] = mapped_column(Integer)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    location: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    recommended_days: Mapped[int | None] = mapped_column(Integer)

    scenario: Mapped[Scenario] = relationship(back_populates="steps")
    rules: Mapped[list[Rule]] = relationship(
        back_populates="scenario_step", cascade="all, delete-orphan"
    )
    sources: Mapped[list[Source]] = relationship(
        secondary=scenario_step_sources, back_populates="scenario_steps"
    )
    documents: Mapped[list[ScenarioStepDocument]] = relationship(
        back_populates="scenario_step", cascade="all, delete-orphan"
    )
    route_steps: Mapped[list[UserRouteStep]] = relationship(back_populates="scenario_step")


class Rule(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rules"

    scenario_step_id: Mapped[UUID] = mapped_column(
        ForeignKey("scenario_steps.id", ondelete="CASCADE"), nullable=False
    )
    field: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[RuleOperator] = mapped_column(
        Enum(RuleOperator, name="rule_operator"), nullable=False
    )
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scenario_step: Mapped[ScenarioStep] = relationship(back_populates="rules")
