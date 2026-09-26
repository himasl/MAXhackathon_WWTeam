import json
from pathlib import Path

from app.core.config import settings
from app.regions.services import RegionalPack, apply_regional_pack, load_regional_pack
from app.scenarios.schemas import ScenarioDefinition


class ScenarioLoader:
    def __init__(
        self, directory: Path | None = None, regional_pack: RegionalPack | None = None
    ) -> None:
        self.directory = directory or settings.scenario_data_dir
        self.regional_pack = regional_pack

    def load(self, code: str) -> ScenarioDefinition:
        path = self.directory / f"{code}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        pack = self.regional_pack if self.regional_pack is not None else load_regional_pack()
        scenario = ScenarioDefinition.model_validate(apply_regional_pack(raw, pack))
        if scenario.code != code:
            raise ValueError(f"Scenario code {scenario.code!r} does not match file {code!r}")
        return scenario

    def load_all(self) -> list[ScenarioDefinition]:
        return [self.load(path.stem) for path in sorted(self.directory.glob("*.json"))]
