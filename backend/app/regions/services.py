"""Regional official sources (data/regional_services.json) and their expansion into scenarios.

The pack is plain data: for each region it may list the regional МФЦ, the territorial
compulsory medical insurance fund (ТФОМС) and the student public-transport discount.
It is applied to the scenario JSON *before* validation, so the rule engine is unchanged:

* ``"regional_sources": ["mfc"]`` on a step links every region's МФЦ source to that step;
  the step card later shows only the source of the user's region.
* ``"regional_template": "student_transport"`` turns one template step into one step per
  region from the pack, each with a ``region_code EQ <code>`` rule and its own source.
* ``"regional_fallback": "student_transport"`` extends the step's ``region_code NOT_IN``
  rule with every region covered by the template, so the fallback shows only elsewhere.
"""

import copy
import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictStr

from app.core.config import settings
from app.regions.catalog import load_regions

RegionalKind = Literal["mfc", "tfoms", "student_transport"]
SOURCE_PREFIX = "region_"

SOURCE_TITLES: dict[str, str] = {
    "mfc": "МФЦ региона: адреса и услуги",
    "tfoms": "Территориальный фонд ОМС региона",
}


class RegionalOffice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization: StrictStr
    url: HttpUrl
    checked_at: date


class StudentTransport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: StrictStr
    # Overrides the template title when the benefit is not a plain city pass.
    step_title: StrictStr | None = None
    title: StrictStr
    url: HttpUrl
    organization: StrictStr
    summary: StrictStr
    documents: list[StrictStr] = Field(default_factory=list)
    checked_at: date


class RegionalServices(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mfc: RegionalOffice | None = None
    tfoms: RegionalOffice | None = None
    student_transport: StudentTransport | None = None

    def kinds(self) -> list[RegionalKind]:
        kinds: list[RegionalKind] = ["mfc", "tfoms", "student_transport"]
        return [kind for kind in kinds if getattr(self, kind) is not None]


class RegionalPack(BaseModel):
    model_config = ConfigDict(extra="ignore")

    regions: dict[StrictStr, RegionalServices] = Field(default_factory=dict)


@lru_cache
def load_regional_pack(path: Path | None = None) -> RegionalPack:
    source = path or settings.regional_services_file
    if not source.is_file():
        return RegionalPack()
    pack = RegionalPack.model_validate(json.loads(source.read_text(encoding="utf-8")))
    unknown = sorted(set(pack.regions) - {region.code for region in load_regions()})
    if unknown:
        raise ValueError(f"Unknown region codes in regional pack: {', '.join(unknown)}")
    return pack


def source_code(kind: str, region_code: str) -> str:
    return f"{SOURCE_PREFIX}{kind}_{region_code}"


def is_regional_source(code: str | None) -> bool:
    return bool(code) and str(code).startswith(SOURCE_PREFIX)


def _region_titles() -> dict[str, str]:
    return {region.code: region.title for region in load_regions()}


def _add_source(sources: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    if all(item.get("code") != entry["code"] for item in sources):
        sources.append(entry)


def apply_regional_pack(raw: dict[str, Any], pack: RegionalPack) -> dict[str, Any]:
    """Expand the regional markers of a scenario dict (see module docstring)."""
    scenario = copy.deepcopy(raw)
    sources: list[dict[str, Any]] = scenario.setdefault("sources", [])
    titles = _region_titles()
    steps: list[dict[str, Any]] = []

    for step in scenario.get("steps", []):
        kinds = step.pop("regional_sources", [])
        for kind in kinds:
            for code, services in pack.regions.items():
                office = getattr(services, kind)
                if office is None:
                    continue
                entry = source_code(kind, code)
                _add_source(
                    sources,
                    {
                        "code": entry,
                        "title": SOURCE_TITLES[kind],
                        "url": str(office.url),
                        "organization": office.organization,
                        "source_type": "OFFICIAL",
                        "region_code": code,
                        "checked_at": office.checked_at.isoformat(),
                    },
                )
                step.setdefault("sources", []).append(entry)

        fallback = step.pop("regional_fallback", None)
        if fallback is not None:
            covered = [code for code, item in pack.regions.items() if getattr(item, fallback)]
            for rule in step.get("rules", []):
                if rule["field"] == "region_code" and rule["operator"] == "NOT_IN":
                    rule["value"] = sorted({*rule["value"], *covered})
                    break
            else:
                step.setdefault("rules", []).append(
                    {"field": "region_code", "operator": "NOT_IN", "value": sorted(covered)}
                )

        template = step.pop("regional_template", None)
        if template is None:
            steps.append(step)
            continue
        steps.extend(_expand_transport(step, pack, titles, sources))

    scenario["steps"] = steps
    return scenario


def _expand_transport(
    template: dict[str, Any],
    pack: RegionalPack,
    titles: dict[str, str],
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for code, services in pack.regions.items():
        transport = services.student_transport
        if transport is None:
            continue
        values = {
            "city": transport.city,
            "region": titles[code],
            "summary": transport.summary,
            "organization": transport.organization,
        }
        step = copy.deepcopy(template)
        step["code"] = f"{template['code']}_{code}"
        for field in ("title", "short_description", "full_description", "reason", "location"):
            if field in step:
                step[field] = step[field].format(**values)
        if transport.step_title:
            step["title"] = transport.step_title
        step["rules"] = [
            {"field": "region_code", "operator": "EQ", "value": code},
            *step.get("rules", []),
        ]
        entry = source_code("transport", code)
        _add_source(
            sources,
            {
                "code": entry,
                "title": transport.title,
                "url": str(transport.url),
                "organization": transport.organization,
                "source_type": "OFFICIAL",
                "region_code": code,
                "checked_at": transport.checked_at.isoformat(),
            },
        )
        step["sources"] = [entry]
        if transport.documents:
            step["documents"] = [{"code": document} for document in transport.documents]
        result.append(step)
    return result


@lru_cache
def regional_coverage() -> dict[str, tuple[RegionalKind, ...]]:
    """Which official regional data each region has, including hand-written scenario steps."""
    from app.scenarios.loader import ScenarioLoader  # local import: loader imports this module

    coverage: dict[str, set[RegionalKind]] = {
        code: set(services.kinds()) for code, services in load_regional_pack().regions.items()
    }
    for scenario in ScenarioLoader().load_all():
        for step in scenario.steps:
            if step.category != "TRANSPORT":
                continue
            for rule in step.rules:
                if rule.field == "region_code" and rule.operator == "EQ":
                    coverage.setdefault(str(rule.value), set()).add("student_transport")
    order: list[RegionalKind] = ["mfc", "tfoms", "student_transport"]
    return {
        code: tuple(kind for kind in order if kind in kinds) for code, kinds in coverage.items()
    }
