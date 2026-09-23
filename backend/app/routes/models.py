from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.scenarios.models import Scenario, ScenarioStep
    from app.users.models import User


class RouteStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class RouteStepStatus(StrEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    SKIPPED = "SKIPPED"


class UserRoute(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_routes"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scenario_id: Mapped[UUID] = mapped_column(
        ForeignKey("scenarios.id", ondelete="RESTRICT"), nullable=False
    )
    scenario_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RouteStatus] = mapped_column(
        Enum(RouteStatus, name="route_status"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="routes")
    scenario: Mapped[Scenario] = relationship()
    steps: Mapped[list[UserRouteStep]] = relationship(
        back_populates="route", cascade="all, delete-orphan", order_by="UserRouteStep.position"
    )


class UserRouteStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_route_steps"
    __table_args__ = (UniqueConstraint("route_id", "scenario_step_id"),)

    route_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_routes.id", ondelete="CASCADE"), nullable=False
    )
    scenario_step_id: Mapped[UUID] = mapped_column(
        ForeignKey("scenario_steps.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RouteStepStatus] = mapped_column(
        Enum(RouteStepStatus, name="route_step_status"), nullable=False
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    route: Mapped[UserRoute] = relationship(back_populates="steps")
    scenario_step: Mapped[ScenarioStep] = relationship(back_populates="route_steps")
