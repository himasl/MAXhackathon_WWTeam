from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictStr

from app.feedback.models import ReportKind


class Count(BaseModel):
    code: str
    title: str
    users: int
    completed: int = 0


class FunnelStage(BaseModel):
    code: str
    title: str
    users: int


class DayActivity(BaseModel):
    day: date
    app: int
    bot: int
    total: int


class StepProblem(BaseModel):
    code: str
    title: str
    in_routes: int
    done: int
    skipped: int
    reports: int
    completion_rate: float


class UsersBlock(BaseModel):
    total: int
    with_profile: int
    with_route: int
    new_7d: int
    new_30d: int


class ActivityBlock(BaseModel):
    dau: int
    wau: int
    mau: int
    # DAU / MAU: how habitual the service is.
    stickiness: float
    # Share of active users who came back on at least one more day.
    returning_share: float
    # Share of active users over 30 days who used the bot (buttons, commands).
    bot_share: float
    daily: list[DayActivity]


class EngagementBlock(BaseModel):
    steps_done: int
    steps_skipped: int
    done_from_chat_share: float
    reminders_sent: int
    reminder_conversion: float
    avg_steps_per_route: float
    completion_rate: float
    route_median_days: float | None
    registration_median_days: float | None


class DataBlock(BaseModel):
    regional_sources: int
    stale_sources: int
    edited_sources: int
    open_reports: int


class AdminOverview(BaseModel):
    """Business metrics for the team. Aggregates only; test accounts are excluded."""

    generated_at: datetime
    users: UsersBlock
    activity: ActivityBlock
    funnel: list[FunnelStage]
    engagement: EngagementBlock
    by_region: list[Count]
    by_university: list[Count]
    by_scenario: list[Count]
    by_housing: list[Count]
    by_language: list[Count]
    problem_steps: list[StepProblem]
    data: DataBlock


class AdminSource(BaseModel):
    id: UUID
    code: str | None
    kind: str
    title: str
    organization: str
    url: str
    region_code: str | None
    region_title: str | None
    checked_at: datetime | None
    stale: bool
    edited_at: datetime | None
    steps: int


class SourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl | None = None
    organization: StrictStr | None = Field(default=None, min_length=2, max_length=255)
    title: StrictStr | None = Field(default=None, min_length=2, max_length=255)
    # «Checked today»: the date of the last check is set to now.
    mark_checked: bool = True


class AdminReport(BaseModel):
    id: UUID
    kind: ReportKind
    comment: str
    summary: str
    step_title: str
    region_code: str | None
    created_at: datetime
    resolved_at: datetime | None
