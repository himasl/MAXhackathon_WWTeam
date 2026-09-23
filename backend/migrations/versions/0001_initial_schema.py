"""Create initial database schema.

Revision ID: 0001_initial_schema
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("max_user_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("max_user_id", name=op.f("uq_users_max_user_id")),
    )
    op.create_table(
        "scenarios",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenarios")),
        sa.UniqueConstraint("code", "version", name=op.f("uq_scenarios_code")),
    )
    op.create_table(
        "sources",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("organization", sa.String(length=255), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum("OFFICIAL", "MOCK", "OTHER", name="source_type"),
            nullable=False,
        ),
        sa.Column("region_code", sa.String(length=32), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
    )
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("region_code", sa.String(length=32), nullable=False),
        sa.Column(
            "education_type",
            sa.Enum("FULL_TIME", "PART_TIME", name="education_type"),
            nullable=False,
        ),
        sa.Column(
            "housing_type",
            sa.Enum("DORMITORY", "RENT", "RELATIVES", "OTHER", name="housing_type"),
            nullable=False,
        ),
        sa.Column("has_registration", sa.Boolean(), nullable=False),
        sa.Column("has_clinic_attachment", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_profiles_user_id")),
    )
    op.create_table(
        "scenario_steps",
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("short_description", sa.Text(), nullable=False),
        sa.Column("full_description", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "REGISTRATION",
                "HEALTHCARE",
                "EDUCATION",
                "TRANSPORT",
                "SOCIAL_SUPPORT",
                "OTHER",
                name="step_category",
            ),
            nullable=False,
        ),
        sa.Column("estimated_duration", sa.Integer(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "estimated_duration >= 0", name=op.f("ck_scenario_steps_estimated_duration_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.id"],
            name=op.f("fk_scenario_steps_scenario_id_scenarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario_steps")),
        sa.UniqueConstraint("scenario_id", "code", name=op.f("uq_scenario_steps_scenario_id")),
    )
    op.create_table(
        "user_routes",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "COMPLETED", "ARCHIVED", name="route_status"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.id"],
            name=op.f("fk_user_routes_scenario_id_scenarios"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_routes_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_routes")),
    )
    op.create_table(
        "rules",
        sa.Column("scenario_step_id", sa.Uuid(), nullable=False),
        sa.Column("field", sa.String(length=100), nullable=False),
        sa.Column(
            "operator",
            sa.Enum("EQ", "NE", "GT", "GTE", "LT", "LTE", "IN", "NOT_IN", name="rule_operator"),
            nullable=False,
        ),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scenario_step_id"],
            ["scenario_steps.id"],
            name=op.f("fk_rules_scenario_step_id_scenario_steps"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rules")),
    )
    op.create_table(
        "scenario_step_sources",
        sa.Column("scenario_step_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scenario_step_id"],
            ["scenario_steps.id"],
            name=op.f("fk_scenario_step_sources_scenario_step_id_scenario_steps"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name=op.f("fk_scenario_step_sources_source_id_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("scenario_step_id", "source_id", name=op.f("pk_scenario_step_sources")),
    )
    op.create_table(
        "user_route_steps",
        sa.Column("route_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_step_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("TODO", "IN_PROGRESS", "DONE", "SKIPPED", name="route_step_status"),
            nullable=False,
        ),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["user_routes.id"],
            name=op.f("fk_user_route_steps_route_id_user_routes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_step_id"],
            ["scenario_steps.id"],
            name=op.f("fk_user_route_steps_scenario_step_id_scenario_steps"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_route_steps")),
        sa.UniqueConstraint(
            "route_id", "scenario_step_id", name=op.f("uq_user_route_steps_route_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("user_route_steps")
    op.drop_table("scenario_step_sources")
    op.drop_table("rules")
    op.drop_table("user_routes")
    op.drop_table("scenario_steps")
    op.drop_table("user_profiles")
    op.drop_table("sources")
    op.drop_table("scenarios")
    op.drop_table("users")

    bind = op.get_bind()
    for enum_name in (
        "route_step_status",
        "rule_operator",
        "route_status",
        "step_category",
        "housing_type",
        "education_type",
        "source_type",
    ):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
