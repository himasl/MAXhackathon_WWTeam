from pathlib import Path

from app.core.config import settings
from app.scenarios.schemas import ScenarioDefinition


class ScenarioLoader:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or settings.scenario_data_dir

    def load(self, code: str) -> ScenarioDefinition:
        path = self.directory / f"{code}.json"
        scenario = ScenarioDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        if scenario.code != code:
            raise ValueError(f"Scenario code {scenario.code!r} does not match file {code!r}")
        return scenario

