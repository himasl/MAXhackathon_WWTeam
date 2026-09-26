"""Feedback on steps: «информация устарела».

Revision ID: 0006_step_reports
Revises: 0005_snooze_share_i18n
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_step_reports"
down_revision: str | None = "0005_snooze_share_i18n"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "step_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("route_step_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("OUTDATED", "NOT_APPLICABLE", "OTHER", name="report_kind"),
            nullable=False,
        ),
        sa.Column("comment", sa.String(length=500), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["route_step_id"],
            ["user_route_steps.id"],
            name=op.f("fk_step_reports_route_step_id_user_route_steps"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_step_reports")),
    )
    op.create_index(
        op.f("ix_step_reports_route_step_id"), "step_reports", ["route_step_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_step_reports_route_step_id"), table_name="step_reports")
    op.drop_table("step_reports")
    sa.Enum(name="report_kind").drop(op.get_bind(), checkfirst=True)
