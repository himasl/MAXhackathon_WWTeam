"""Add universities, scenario audience, citizenship and completion channel.

Revision ID: 0003_universities_audience
Revises: 0002_documents_and_step_details
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_universities_audience"
down_revision: str | None = "0002_documents_and_step_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

citizenship = sa.Enum("RU", "FOREIGN", name="citizenship")


def upgrade() -> None:
    op.create_table(
        "universities",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("short_title", sa.String(length=100), nullable=False),
        sa.Column("region_code", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_universities")),
        sa.UniqueConstraint("code", name=op.f("uq_universities_code")),
    )

    citizenship.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "user_profiles",
        sa.Column("citizenship", citizenship, server_default="RU", nullable=False),
    )
    op.add_column(
        "user_profiles", sa.Column("university_code", sa.String(length=50), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_user_profiles_university_code_universities"),
        "user_profiles",
        "universities",
        ["university_code"],
        ["code"],
        ondelete="SET NULL",
    )

    op.add_column(
        "scenarios",
        sa.Column(
            "audience",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )
    op.add_column(
        "user_route_steps", sa.Column("completed_via", sa.String(length=16), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_route_steps", "completed_via")
    op.drop_column("scenarios", "audience")
    op.drop_constraint(
        op.f("fk_user_profiles_university_code_universities"),
        "user_profiles",
        type_="foreignkey",
    )
    op.drop_column("user_profiles", "university_code")
    op.drop_column("user_profiles", "citizenship")
    citizenship.drop(op.get_bind(), checkfirst=True)
    op.drop_table("universities")
