from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.scenarios.models import Scenario, ScenarioStep


class ScenarioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(self) -> Scenario | None:
        query = (
            select(Scenario)
            .where(Scenario.is_active.is_(True))
            .options(
                selectinload(Scenario.steps).selectinload(ScenarioStep.rules),
                selectinload(Scenario.steps).selectinload(ScenarioStep.sources),
            )
            .order_by(Scenario.version.desc(), Scenario.code)
            .limit(1)
        )
        return cast(Scenario | None, await self.session.scalar(query))
