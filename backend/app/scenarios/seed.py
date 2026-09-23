"""Synchronise scenario JSON files from ``SCENARIO_DATA_DIR`` into PostgreSQL.

A scenario is identified by ``(code, version)``. Existing versions are never rewritten,
because user routes reference their steps; publish a new ``version`` to change content.
Sources and documents are upserted by ``code``.
"""

import asyncio
import logging
from datetime import UTC, date, datetime, time
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as _models
from app.core.config import settings
from app.core.database import async_session
from app.documents.models import Document, ScenarioStepDocument
from app.scenarios.loader import ScenarioLoader
from app.scenarios.models import Rule, Scenario, ScenarioStep
from app.scenarios.schemas import ScenarioDefinition
from app.sources.models import Source
from app.universities.models import University
from app.universities.schemas import UniversityCatalog, UniversityDefinition

logger = logging.getLogger(__name__)
_MODELS_LOADED = _models


def _as_datetime(value: date | None) -> datetime | None:
    return None if value is None else datetime.combine(value, time(), tzinfo=UTC)


async def _upsert_sources(
    session: AsyncSession, definition: ScenarioDefinition
) -> dict[str, Source]:
    result: dict[str, Source] = {}
    for item in definition.sources:
        source = await session.scalar(select(Source).where(Source.code == item.code))
        if source is None:
            source = Source(code=item.code)
            session.add(source)
        source.title = item.title
        source.url = str(item.url)
        source.organization = item.organization
        source.source_type = item.source_type
        source.region_code = item.region_code
        source.published_at = _as_datetime(item.published_at)
        source.checked_at = _as_datetime(item.checked_at)
        result[item.code] = source
    return result


async def _upsert_documents(
    session: AsyncSession, definition: ScenarioDefinition
) -> dict[str, Document]:
    result: dict[str, Document] = {}
    for item in definition.documents:
        document = await session.scalar(select(Document).where(Document.code == item.code))
        if document is None:
            document = Document(code=item.code)
            session.add(document)
        document.title = item.title
        document.description = item.description
        result[item.code] = document
    return result


async def upsert_universities(
    session: AsyncSession, items: list[UniversityDefinition]
) -> None:
    for position, item in enumerate(items):
        university = await session.scalar(select(University).where(University.code == item.code))
        if university is None:
            university = University(code=item.code)
            session.add(university)
        university.title = item.title
        university.short_title = item.short_title
        university.region_code = item.region_code
        university.kind = item.kind
        university.partner = item.partner
        university.popular = item.popular
        university.sort_order = position
    await session.flush()


def load_universities(path: Path | None = None) -> list[UniversityDefinition]:
    source = path or settings.universities_file
    if not source.is_file():
        logger.warning("Universities catalog %s not found", source)
        return []
    catalog = UniversityCatalog.model_validate_json(source.read_text(encoding="utf-8"))
    codes = [item.code for item in catalog.institutions]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        raise ValueError(f"Duplicate university codes: {', '.join(duplicates)}")
    return catalog.institutions


async def sync_scenario(session: AsyncSession, definition: ScenarioDefinition) -> bool:
    """Create the scenario version if missing. Returns True when something was created."""
    await upsert_universities(session, definition.universities)
    sources = await _upsert_sources(session, definition)
    documents = await _upsert_documents(session, definition)

    existing = await session.scalar(
        select(Scenario).where(
            Scenario.code == definition.code, Scenario.version == definition.version
        )
    )
    if existing is not None:
        await session.flush()
        return False

    if definition.is_active:
        await session.execute(
            update(Scenario).where(Scenario.code == definition.code).values(is_active=False)
        )

    scenario = Scenario(
        code=definition.code,
        title=definition.title,
        description=definition.description,
        version=definition.version,
        is_active=definition.is_active,
        audience=[rule.model_dump(mode="json") for rule in definition.audience],
        steps=[
            ScenarioStep(
                code=step.code,
                title=step.title,
                short_description=step.short_description,
                full_description=step.full_description,
                reason=step.reason,
                location=step.location,
                position=step.position,
                category=step.category,
                estimated_duration=step.estimated_duration,
                recommended_days=step.recommended_days,
                is_required=step.is_required,
                rules=[
                    Rule(field=rule.field, operator=rule.operator, value=rule.value)
                    for rule in step.rules
                ],
                sources=[sources[code] for code in step.sources],
                documents=[
                    ScenarioStepDocument(document=documents[item.code], required=item.required)
                    for item in step.documents
                ],
            )
            for step in definition.steps
        ],
    )
    session.add(scenario)
    await session.flush()
    return True


async def sync_all(
    session: AsyncSession,
    loader: ScenarioLoader | None = None,
    universities_file: Path | None = None,
) -> int:
    await upsert_universities(session, load_universities(universities_file))
    created = 0
    for definition in (loader or ScenarioLoader()).load_all():
        if await sync_scenario(session, definition):
            created += 1
            logger.info("Scenario %s v%s created", definition.code, definition.version)
    await session.commit()
    return created


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    async with async_session() as session:
        created = await sync_all(session)
    logger.info("Scenario sync finished, %s new version(s)", created)


if __name__ == "__main__":
    asyncio.run(main())
