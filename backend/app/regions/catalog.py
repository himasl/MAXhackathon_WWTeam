"""Catalog of the constituent entities of the Russian Federation (data/regions.json)."""

import json
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

from app.core.config import settings


class Region(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: StrictStr = Field(pattern=r"^\d{2}$")
    title: StrictStr
    popular: StrictBool = False
    # IANA zone of the regional capital: quiet hours and weekly digests use local time.
    timezone: StrictStr = "Europe/Moscow"


class RegionCatalog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    regions: list[Region]


@lru_cache
def load_regions(path: Path | None = None) -> tuple[Region, ...]:
    source = path or settings.regions_file
    catalog = RegionCatalog.model_validate(json.loads(source.read_text(encoding="utf-8")))
    codes = [region.code for region in catalog.regions]
    if len(codes) != len(set(codes)):
        raise ValueError("Duplicate region codes in regions catalog")
    return tuple(catalog.regions)


def region_codes() -> set[str]:
    return {region.code for region in load_regions()}


def region_timezone(code: str | None) -> ZoneInfo:
    zones = {region.code: region.timezone for region in load_regions()}
    return ZoneInfo(zones.get(code or "", "Europe/Moscow"))
