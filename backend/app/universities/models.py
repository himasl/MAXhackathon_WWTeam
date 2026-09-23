from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPrimaryKeyMixin


class University(UUIDPrimaryKeyMixin, Base):
    """University or college from data/universities.json.

    Partner universities have their own official steps in scenario JSON (rule on code);
    the others are used for selection, invitations and pilot statistics.
    """

    __tablename__ = "universities"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_title: Mapped[str] = mapped_column(String(100), nullable=False)
    region_code: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="university", server_default="university"
    )
    partner: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    popular: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
