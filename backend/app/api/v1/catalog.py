from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.dependencies import SessionDependency
from app.api.errors import ERROR_RESPONSES
from app.core.config import settings
from app.universities.repository import UniversityRepository
from app.universities.schemas import UniversityResponse

router = APIRouter(tags=["catalog"], responses=ERROR_RESPONSES)


class AppConfigResponse(BaseModel):
    bot_username: str | None
    bot_url: str | None


@router.get("/config", response_model=AppConfigResponse)
async def get_config() -> AppConfigResponse:
    """Public client settings: the bot link used for invitations."""
    username = settings.max_bot_username or None
    return AppConfigResponse(
        bot_username=username,
        bot_url=f"https://max.ru/{username}" if username else None,
    )


@router.get("/universities", response_model=list[UniversityResponse])
async def list_universities(
    session: SessionDependency,
    region_code: Annotated[str | None, Query(max_length=32)] = None,
) -> list[UniversityResponse]:
    """Pilot partner universities, optionally filtered by region."""
    universities = await UniversityRepository(session).list(region_code)
    return [
        UniversityResponse.model_validate(item, from_attributes=True) for item in universities
    ]
