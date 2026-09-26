from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.feedback.models import ReportKind


class StepReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ReportKind
    comment: str = Field(default="", max_length=500)


class StepReportResponse(BaseModel):
    id: UUID
    kind: ReportKind
