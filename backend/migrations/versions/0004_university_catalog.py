"""University catalog: institution kind, partner and popular flags, display order.

Revision ID: 0004_university_catalog
Revises: 0003_universities_audience
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_university_catalog"
down_revision: str | None = "0003_universities_audience"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "universities",
        sa.Column("kind", sa.String(length=16), server_default="university", nullable=False),
    )
    op.add_column(
        "universities",
        sa.Column("partner", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "universities",
        sa.Column("popular", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "universities",
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("universities", "sort_order")
    op.drop_column("universities", "popular")
    op.drop_column("universities", "partner")
    op.drop_column("universities", "kind")
