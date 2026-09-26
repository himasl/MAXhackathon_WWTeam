from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.scenarios.models import ScenarioStep


class Document(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "documents"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    i18n: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )


class ScenarioStepDocument(Base):
    __tablename__ = "scenario_step_documents"

    scenario_step_id: Mapped[UUID] = mapped_column(
        ForeignKey("scenario_steps.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    scenario_step: Mapped[ScenarioStep] = relationship(back_populates="documents")
    document: Mapped[Document] = relationship()
