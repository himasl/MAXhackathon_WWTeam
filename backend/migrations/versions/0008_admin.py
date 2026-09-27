"""Team panel: daily activity per channel, admin edits of sources, resolved reports.

Revision ID: 0008_admin
Revises: 0007_lang_digests
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_admin"
down_revision: str | None = "0007_lang_digests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_activity",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("channel", sa.String(length=8), primary_key=True),
    )
    op.create_index("ix_user_activity_day", "user_activity", ["day"])
    op.add_column("sources", sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sources", sa.Column("edited_by", sa.BigInteger(), nullable=True))
    op.add_column(
        "step_reports", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("step_reports", "resolved_at")
    op.drop_column("sources", "edited_by")
    op.drop_column("sources", "edited_at")
    op.drop_index("ix_user_activity_day", table_name="user_activity")
    op.drop_table("user_activity")
