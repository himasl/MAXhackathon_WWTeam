import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.scenarios.loader import ScenarioLoader


def write_scenario(directory: Path, data: dict[str, Any]) -> None:
    directory.joinpath("student_relocation_v1.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


def scenario_data() -> dict[str, Any]:
    return {
        "code": "student_relocation_v1",
        "version": 1,
        "steps": [
            {
                "code": "temporary_registration",
                "title": "Проверьте вопрос регистрации",
                "position": 10,
                "category": "REGISTRATION",
                "rules": [
                    {
                        "field": "has_registration",
                        "operator": "EQ",
                        "value": False,
                    }
                ],
            }
        ],
    }


def test_load_scenario_from_json(tmp_path: Path) -> None:
    write_scenario(tmp_path, scenario_data())

    scenario = ScenarioLoader(tmp_path).load("student_relocation_v1")

    assert scenario.code == "student_relocation_v1"
    assert scenario.version == 1
    assert scenario.steps[0].position == 10
    assert scenario.steps[0].rules[0].value is False


def test_loader_rejects_unknown_rule_field(tmp_path: Path) -> None:
    data = scenario_data()
    data["steps"][0]["rules"][0]["field"] = "unknown"
    write_scenario(tmp_path, data)

    with pytest.raises(ValidationError):
        ScenarioLoader(tmp_path).load("student_relocation_v1")


@pytest.mark.parametrize("operator", ["IN", "NOT_IN"])
def test_loader_rejects_scalar_membership_value(tmp_path: Path, operator: str) -> None:
    data = scenario_data()
    data["steps"][0]["rules"][0] = {
        "field": "region_code",
        "operator": operator,
        "value": "77",
    }
    write_scenario(tmp_path, data)

    with pytest.raises(ValidationError, match="requires an array value"):
        ScenarioLoader(tmp_path).load("student_relocation_v1")


def test_loader_rejects_mismatched_file_code(tmp_path: Path) -> None:
    data = scenario_data()
    data["code"] = "another_scenario"
    write_scenario(tmp_path, data)

    with pytest.raises(ValueError, match="does not match"):
        ScenarioLoader(tmp_path).load("student_relocation_v1")
