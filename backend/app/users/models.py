from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.routes.models import UserRoute


class Citizenship(StrEnum):
    RU = "RU"
    FOREIGN = "FOREIGN"


class EducationType(StrEnum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"


class HousingType(StrEnum):
    DORMITORY = "DORMITORY"
    RENT = "RENT"
    RELATIVES = "RELATIVES"
    OTHER = "OTHER"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    max_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    # Part of every parent (progress) link; incrementing it revokes all issued links.
    share_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Interface language chosen in the app: bot messages use it too ("ru" / "en").
    lang: Mapped[str] = mapped_column(String(2), nullable=False, default="ru", server_default="ru")
    digest_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped[UserProfile | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    routes: Mapped[list[UserRoute]] = relationship(back_populates="user")


class UserProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    region_code: Mapped[str] = mapped_column(String(32), nullable=False)
    education_type: Mapped[EducationType] = mapped_column(
        Enum(EducationType, name="education_type"), nullable=False
    )
    housing_type: Mapped[HousingType] = mapped_column(
        Enum(HousingType, name="housing_type"), nullable=False
    )
    has_registration: Mapped[bool] = mapped_column(Boolean, nullable=False)
    has_clinic_attachment: Mapped[bool] = mapped_column(Boolean, nullable=False)
    citizenship: Mapped[Citizenship] = mapped_column(
        Enum(Citizenship, name="citizenship"),
        nullable=False,
        default=Citizenship.RU,
        server_default=Citizenship.RU.value,
    )
    university_code: Mapped[str | None] = mapped_column(
        ForeignKey("universities.code", ondelete="SET NULL")
    )

    user: Mapped[User] = relationship(back_populates="profile")
