from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.sources.models import SourceType


class SourceResponse(BaseModel):
    id: UUID
    title: str
    url: str
    organization: str
    source_type: SourceType
    region_code: str | None
    published_at: datetime | None
    checked_at: datetime | None

