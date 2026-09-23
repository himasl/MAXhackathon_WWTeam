from pydantic import BaseModel, ConfigDict, Field, StrictStr

CODE_PATTERN = r"^[a-z0-9_]+$"


class UniversityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: StrictStr = Field(pattern=CODE_PATTERN, max_length=50)
    title: StrictStr
    short_title: StrictStr
    region_code: StrictStr


class UniversityResponse(BaseModel):
    code: str
    title: str
    short_title: str
    region_code: str
