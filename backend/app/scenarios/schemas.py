from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from app.rules.schemas import RuleDefinition
from app.scenarios.models import StepCategory


class ScenarioStepDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: StrictStr
    title: StrictStr
    short_description: StrictStr = ""
    full_description: StrictStr = ""
    position: StrictInt = Field(ge=0)
    category: StepCategory
    estimated_duration: StrictInt | None = Field(default=None, ge=0)
    is_required: StrictBool = True
    rules: list[RuleDefinition] = Field(default_factory=list)


class ScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: StrictStr
    title: StrictStr = ""
    description: StrictStr = ""
    version: StrictInt = Field(gt=0)
    is_active: StrictBool = True
    steps: list[ScenarioStepDefinition]

