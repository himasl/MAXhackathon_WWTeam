"""Add documents, step explanations, source codes and reminders.

Revision ID: 0002_documents_and_step_details
Revises: 0001_initial_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_documents_and_step_details"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scenario_steps", sa.Column("reason", sa.Text(), server_default="", nullable=False)
    )
    op.add_column(
        "scenario_steps", sa.Column("location", sa.Text(), server_default="", nullable=False)
    )
    op.add_column("scenario_steps", sa.Column("recommended_days", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_scenario_steps_recommended_days_non_negative"),
        "scenario_steps",
        "recommended_days >= 0",
    )

    op.add_column("sources", sa.Column("code", sa.String(length=100), nullable=True))
    op.create_unique_constraint(op.f("uq_sources_code"), "sources", ["code"])

    op.add_column(
        "user_route_steps",
        sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "documents",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("code", name=op.f("uq_documents_code")),
    )
    op.create_table(
        "scenario_step_documents",
        sa.Column("scenario_step_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_scenario_step_documents_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_step_id"],
            ["scenario_steps.id"],
            name=op.f("fk_scenario_step_documents_scenario_step_id_scenario_steps"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "scenario_step_id", "document_id", name=op.f("pk_scenario_step_documents")
        ),
    )


def downgrade() -> None:
    op.drop_table("scenario_step_documents")
    op.drop_table("documents")
    op.drop_column("user_route_steps", "reminded_at")
    op.drop_constraint(op.f("uq_sources_code"), "sources", type_="unique")
    op.drop_column("sources", "code")
    op.drop_constraint(
        op.f("ck_scenario_steps_recommended_days_non_negative"), "scenario_steps", type_="check"
    )
    op.drop_column("scenario_steps", "recommended_days")
    op.drop_column("scenario_steps", "location")
    op.drop_column("scenario_steps", "reason")
