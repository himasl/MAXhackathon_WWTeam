"""Questions to the assistant and the contract of an external RAG service.

The contract (``RagRequest`` → ``RagResponse``) is what a RAG service must implement:
see docs/rag.md."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictStr

Provider = Literal["rag", "stub", "none"]


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: StrictStr = Field(min_length=3, max_length=500)
    # The step the student is looking at, when the question is asked from a step card.
    step_id: UUID | None = None


class AnswerSource(BaseModel):
    title: StrictStr
    url: StrictStr
    organization: StrictStr = ""


class AskResponse(BaseModel):
    answer: str
    sources: list[AnswerSource]
    # A step of the route the answer is about: the app/bot offer to open it.
    step_id: UUID | None = None
    # Who answered: the external RAG service, the built-in search over the route, or nobody.
    provider: Provider
    # True when the RAG service was configured but did not answer in time or failed.
    fallback: bool = False


# ---- the contract of the external RAG service (POST RAG_URL) ----


class RagSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: StrictStr = Field(min_length=1, max_length=300)
    url: HttpUrl
    organization: StrictStr = ""


class RagStep(BaseModel):
    """A step of the student's route, as context for retrieval and for the answer."""

    code: str
    title: str
    short_description: str
    full_description: str = ""
    location: str = ""
    sources: list[AnswerSource] = Field(default_factory=list)


class RagRequest(BaseModel):
    question: str
    lang: Literal["ru", "en"]
    region_code: str | None = None
    region_title: str | None = None
    citizenship: Literal["RU", "FOREIGN"] | None = None
    university_code: str | None = None
    # The step the question is about (from a step card), if any.
    step: RagStep | None = None
    # The whole route: what the student has to do, with official sources.
    route: list[RagStep] = Field(default_factory=list)


class RagResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answer: StrictStr = Field(min_length=1, max_length=4000)
    sources: list[RagSource] = Field(default_factory=list)
    # Optional: the code of a route step the answer refers to.
    step_code: StrictStr | None = None
