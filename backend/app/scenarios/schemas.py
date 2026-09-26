from datetime import date
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.rules.schemas import RuleDefinition
from app.scenarios.models import StepCategory
from app.sources.models import SourceType
from app.universities.schemas import UniversityDefinition

CODE_PATTERN = r"^[a-z0-9_]+$"

# Languages scenario texts can be translated to (Russian is the source language).
Language = Literal["en"]


class StepTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: StrictStr
    short_description: StrictStr = ""
    full_description: StrictStr = ""
    reason: StrictStr = ""
    location: StrictStr = ""


class DocumentTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: StrictStr
    description: StrictStr = ""


class SourceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: StrictStr = Field(pattern=CODE_PATTERN)
    title: StrictStr
    url: HttpUrl
    organization: StrictStr
    source_type: SourceType
    region_code: StrictStr | None = None
    published_at: date | None = None
    checked_at: date | None = None


class DocumentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: StrictStr = Field(pattern=CODE_PATTERN)
    title: StrictStr
    description: StrictStr = ""
    i18n: dict[Language, DocumentTranslation] = Field(default_factory=dict)


class StepDocumentReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: StrictStr
    required: StrictBool = True


class ScenarioStepDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: StrictStr = Field(pattern=CODE_PATTERN)
    title: StrictStr
    short_description: StrictStr = ""
    full_description: StrictStr = ""
    reason: StrictStr = ""
    location: StrictStr = ""
    position: StrictInt = Field(ge=0)
    category: StepCategory
    estimated_duration: StrictInt | None = Field(default=None, ge=0)
    recommended_days: StrictInt | None = Field(default=None, ge=0)
    is_required: StrictBool = True
    rules: list[RuleDefinition] = Field(default_factory=list)
    sources: list[StrictStr] = Field(default_factory=list)
    documents: list[StepDocumentReference] = Field(default_factory=list)
    i18n: dict[Language, StepTranslation] = Field(default_factory=dict)


class ScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: StrictStr = Field(pattern=CODE_PATTERN)
    title: StrictStr = ""
    description: StrictStr = ""
    version: StrictInt = Field(gt=0)
    is_active: StrictBool = True
    # Who the scenario is for, e.g. citizenship EQ RU. Empty list = everyone.
    audience: list[RuleDefinition] = Field(default_factory=list)
    universities: list[UniversityDefinition] = Field(default_factory=list)
    sources: list[SourceDefinition] = Field(default_factory=list)
    documents: list[DocumentDefinition] = Field(default_factory=list)
    steps: list[ScenarioStepDefinition]

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        for kind, codes in (
            ("step", [step.code for step in self.steps]),
            ("source", [source.code for source in self.sources]),
            ("document", [document.code for document in self.documents]),
            ("university", [university.code for university in self.universities]),
        ):
            duplicates = sorted({code for code in codes if codes.count(code) > 1})
            if duplicates:
                raise ValueError(f"Duplicate {kind} codes: {', '.join(duplicates)}")

        source_codes = {source.code for source in self.sources}
        document_codes = {document.code for document in self.documents}
        for step in self.steps:
            unknown_sources = set(step.sources) - source_codes
            if unknown_sources:
                raise ValueError(
                    f"Step {step.code} references unknown sources: "
                    f"{', '.join(sorted(unknown_sources))}"
                )
            unknown_documents = {item.code for item in step.documents} - document_codes
            if unknown_documents:
                raise ValueError(
                    f"Step {step.code} references unknown documents: "
                    f"{', '.join(sorted(unknown_documents))}"
                )
        return self
