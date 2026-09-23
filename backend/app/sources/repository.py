from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.sources.models import Source, scenario_step_sources


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_step(self, scenario_step_id: UUID) -> list[Source]:
        query = (
            select(Source)
            .join(
                scenario_step_sources,
                scenario_step_sources.c.source_id == Source.id,
            )
            .where(scenario_step_sources.c.scenario_step_id == scenario_step_id)
            .order_by(Source.title)
        )
        return list(await self.session.scalars(query))

