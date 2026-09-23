from sqlalchemy import CheckConstraint, DateTime, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401
from app.core.database import Base


def test_model_registry_contains_all_tables() -> None:
    configure_mappers()

    assert set(Base.metadata.tables) == {
        "documents",
        "scenario_step_documents",
        "rules",
        "scenario_step_sources",
        "scenario_steps",
        "scenarios",
        "sources",
        "user_profiles",
        "user_route_steps",
        "user_routes",
        "users",
    }


def test_database_types_match_specification() -> None:
    tables = Base.metadata.tables

    for table_name in set(tables) - {"scenario_step_sources", "scenario_step_documents"}:
        assert isinstance(tables[table_name].c.id.type, Uuid)

    assert isinstance(tables["rules"].c.value.type, JSONB)
    assert tables["scenario_steps"].c.estimated_duration.nullable
    assert any(
        isinstance(constraint, CheckConstraint)
        and str(constraint.sqltext) == "estimated_duration >= 0"
        for constraint in tables["scenario_steps"].constraints
    )

    for table in tables.values():
        for column_name in (
            "created_at",
            "updated_at",
            "completed_at",
            "deadline",
            "published_at",
            "checked_at",
        ):
            if column_name in table.c:
                column_type = table.c[column_name].type
                assert isinstance(column_type, DateTime)
                assert column_type.timezone is True
