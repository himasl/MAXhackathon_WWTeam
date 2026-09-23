from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.routes.models import UserRoute


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

    user: Mapped[User] = relationship(back_populates="profile")
