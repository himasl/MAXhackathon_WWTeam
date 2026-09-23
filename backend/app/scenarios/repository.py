from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.documents.models import ScenarioStepDocument
from app.scenarios.models import Scenario, ScenarioStep


class ScenarioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> list[Scenario]:
        query = (
            select(Scenario)
            .where(Scenario.is_active.is_(True))
            .options(
                selectinload(Scenario.steps).selectinload(ScenarioStep.rules),
                selectinload(Scenario.steps).selectinload(ScenarioStep.sources),
                selectinload(Scenario.steps)
                .selectinload(ScenarioStep.documents)
                .joinedload(ScenarioStepDocument.document),
            )
            .order_by(Scenario.code, Scenario.version.desc())
        )
        return list(await self.session.scalars(query))
