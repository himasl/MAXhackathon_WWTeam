from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPrimaryKeyMixin


class University(UUIDPrimaryKeyMixin, Base):
    """Partner university of a pilot. Its own steps live in scenario JSON (rule on code)."""

    __tablename__ = "universities"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_title: Mapped[str] = mapped_column(String(100), nullable=False)
    region_code: Mapped[str] = mapped_column(String(32), nullable=False)
