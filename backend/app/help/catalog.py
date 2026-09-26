"""«Если что-то пошло не так»: short situations with actions, phones and official links
(data/help.json). Russian is the source language; ``i18n.en`` translates the texts."""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictStr

from app.core.config import settings


class HelpPhone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: StrictStr
    number: StrictStr


class HelpSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: StrictStr
    url: HttpUrl
    organization: StrictStr


class HelpTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: StrictStr
    summary: StrictStr
    actions: list[StrictStr]
    # Labels of ``phones`` in the same order.
    phones: list[StrictStr] = Field(default_factory=list)


class HelpTopic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: StrictStr
    title: StrictStr
    summary: StrictStr
    actions: list[StrictStr]
    phones: list[HelpPhone] = Field(default_factory=list)
    sources: list[HelpSource] = Field(default_factory=list)
    i18n: dict[StrictStr, HelpTranslation] = Field(default_factory=dict, exclude=True)

    def localized(self, lang: str) -> "HelpTopic":
        text = self.i18n.get(lang)
        if text is None:
            return self
        phones = [
            HelpPhone(label=label, number=phone.number)
            for phone, label in zip(self.phones, text.phones or [p.label for p in self.phones])
        ]
        return self.model_copy(
            update={
                "title": text.title,
                "summary": text.summary,
                "actions": text.actions,
                "phones": phones,
            }
        )


class HelpCatalog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topics: list[HelpTopic]


@lru_cache
def load_help(path: Path | None = None) -> tuple[HelpTopic, ...]:
    source = path or settings.help_file
    if not source.is_file():
        return ()
    return tuple(HelpCatalog.model_validate_json(source.read_text(encoding="utf-8")).topics)
