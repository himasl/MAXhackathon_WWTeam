from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.regions.services import is_regional_source
from app.sources.repository import SourceRepository
from app.sources.schemas import SourceResponse


class SourceService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = SourceRepository(session)

    async def list_for_step(
        self, scenario_step_id: UUID, region_code: str | None = None
    ) -> list[SourceResponse]:
        """Sources of a step; regional pack sources only for ``region_code``."""
        sources = await self.repository.list_for_step(scenario_step_id)
        return [
            SourceResponse.model_validate(source, from_attributes=True)
            for source in sources
            if not is_regional_source(source.code) or source.region_code == region_code
        ]
