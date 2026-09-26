"""Chat snooze, revocable parent links, translations of scenario texts.

Revision ID: 0005_snooze_share_i18n
Revises: 0004_university_catalog
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_snooze_share_i18n"
down_revision: str | None = "0004_university_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_route_steps", sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users", sa.Column("share_version", sa.Integer(), server_default="0", nullable=False)
    )
    for table in ("scenario_steps", "documents"):
        op.add_column(
            table,
            sa.Column(
                "i18n",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default="{}",
                nullable=False,
            ),
        )


def downgrade() -> None:
    for table in ("documents", "scenario_steps"):
        op.drop_column(table, "i18n")
    op.drop_column("users", "share_version")
    op.drop_column("user_route_steps", "snoozed_until")
