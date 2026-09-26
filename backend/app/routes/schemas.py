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
    short_description: str
    category: StepCategory
    position: int
    status: RouteStepStatus
    is_required: bool
    estimated_duration: int | None
    deadline: datetime | None


class RouteResponse(BaseModel):
    id: UUID
    status: RouteStatus
    scenario_code: str
    scenario_version: int
    created_at: datetime
    completed_at: datetime | None
    progress: RouteProgress
    next_step_id: UUID | None
    steps: list[RouteStepSummary]


class StepDocumentResponse(BaseModel):
    code: str
    title: str
    description: str
    required: bool


class RouteStepDetailResponse(BaseModel):
    id: UUID
    route_id: UUID
    code: str
    title: str
    short_description: str
    full_description: str
    reason: str
    location: str
    category: StepCategory
    estimated_duration: int | None
    is_required: bool
    position: int
    status: RouteStepStatus
    deadline: datetime | None
    deadline_origin: str | None
    completed_at: datetime | None
    documents: list[StepDocumentResponse]
    sources: list[SourceResponse]
    next_step_id: UUID | None


class CalendarLinkResponse(BaseModel):
    url: str
    expires_in: int


class ReminderResponse(BaseModel):
    sent: bool
    step_id: UUID | None


class ChecklistGroup(BaseModel):
    """Documents to take to one place, gathered from the open steps that go there."""

    place: str
    steps: list[str]
    documents: list[StepDocumentResponse]


class ChecklistResponse(BaseModel):
    groups: list[ChecklistGroup]


class ChecklistSentResponse(BaseModel):
    sent: bool


class ShareLinkResponse(BaseModel):
    url: str
    expires_in: int


class SharedStep(BaseModel):
    title: str
    category: StepCategory
    status: RouteStepStatus
    completed_at: datetime | None


class SharedProgressResponse(BaseModel):
    """What a parent sees by the link: step titles and progress only, no personal data."""

    status: RouteStatus
    progress: RouteProgress
    created_at: datetime
    completed_at: datetime | None
    steps: list[SharedStep]
