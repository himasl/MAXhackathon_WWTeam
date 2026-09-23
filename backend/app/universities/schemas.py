from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

CODE_PATTERN = r"^[a-z0-9_]+$"
type InstitutionKind = Literal["university", "college"]


class UniversityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: StrictStr = Field(pattern=CODE_PATTERN, max_length=50)
    title: StrictStr
    short_title: StrictStr
    region_code: StrictStr = Field(pattern=r"^\d{2}$")
    kind: InstitutionKind = "university"
    partner: StrictBool = False
    popular: StrictBool = False


class UniversityCatalog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    institutions: list[UniversityDefinition]


class UniversityResponse(BaseModel):
    code: str
    title: str
    short_title: str
    region_code: str
    kind: InstitutionKind
    partner: bool
    popular: bool
