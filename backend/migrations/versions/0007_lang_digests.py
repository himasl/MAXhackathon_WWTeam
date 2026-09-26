"""User language for bot messages, weekly digest mark, daily digest of step reports.

Revision ID: 0007_lang_digests
Revises: 0006_step_reports
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_lang_digests"
down_revision: str | None = "0006_step_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("lang", sa.String(length=2), server_default="ru", nullable=False)
    )
    op.add_column("users", sa.Column("digest_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "step_reports", sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "step_reports", sa.Column("summary", sa.Text(), server_default="", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("step_reports", "summary")
    op.drop_column("step_reports", "notified_at")
    op.drop_column("users", "digest_sent_at")
    op.drop_column("users", "lang")
