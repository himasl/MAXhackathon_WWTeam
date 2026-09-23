from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.sources.repository import SourceRepository
from app.sources.schemas import SourceResponse


class SourceService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = SourceRepository(session)

    async def list_for_step(self, scenario_step_id: UUID) -> list[SourceResponse]:
        sources = await self.repository.list_for_step(scenario_step_id)
        return [SourceResponse.model_validate(source, from_attributes=True) for source in sources]

