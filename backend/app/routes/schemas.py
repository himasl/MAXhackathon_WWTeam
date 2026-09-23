from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.routes.models import RouteStatus, RouteStepStatus
from app.scenarios.models import StepCategory
from app.scenarios.schemas import ScenarioStepDefinition
from app.sources.schemas import SourceResponse


class GeneratedRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_code: str
    scenario_version: int
    steps: list[ScenarioStepDefinition]


class RouteProgress(BaseModel):
    completed: int
    total: int
    percent: int


class RouteStepSummary(BaseModel):
    id: UUID
    code: str
    title: str
    position: int
    status: RouteStepStatus
    deadline: datetime | None


class RouteResponse(BaseModel):
    id: UUID
    status: RouteStatus
    scenario_code: str
    scenario_version: int
    progress: RouteProgress
    steps: list[RouteStepSummary]


class RouteStepDetailResponse(BaseModel):
    id: UUID
    code: str
    title: str
    short_description: str
    full_description: str
    category: StepCategory
    estimated_duration: int | None
    position: int
    status: RouteStepStatus
    deadline: datetime | None
    sources: list[SourceResponse]
