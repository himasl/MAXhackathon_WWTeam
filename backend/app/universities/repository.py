from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.universities.models import University


class UniversityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, code: str) -> University | None:
        return cast(
            University | None,
            await self.session.scalar(select(University).where(University.code == code)),
        )

    async def list(self, region_code: str | None = None) -> list[University]:
        query = select(University).order_by(University.title)
        if region_code is not None:
            query = query.where(University.region_code == region_code)
        return list(await self.session.scalars(query))
