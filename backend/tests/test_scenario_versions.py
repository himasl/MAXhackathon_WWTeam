"""Guard: changing a scenario (or the regional pack it expands) requires a new ``version``.

Published versions are never rewritten in the database, so an edit without a version bump
would silently not reach production. When this test fails: raise ``version`` in the
scenario JSON and run ``python -m tests.test_scenario_versions`` to record the new hash.
"""

import hashlib
import json
from pathlib import Path

from app.scenarios.loader import ScenarioLoader

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"
FINGERPRINTS = Path(__file__).with_name("scenario_fingerprints.json")


def fingerprints() -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for scenario in ScenarioLoader(DATA_DIR).load_all():
        content = scenario.model_dump(mode="json", exclude={"version"})
        digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        result[scenario.code] = {"version": scenario.version, "sha256": digest}
    return result


def test_changed_scenarios_have_new_versions() -> None:
    recorded = json.loads(FINGERPRINTS.read_text(encoding="utf-8"))
    for code, current in fingerprints().items():
        previous = recorded.get(code)
        if previous is None or previous["sha256"] == current["sha256"]:
            continue
        assert current["version"] != previous["version"], (
            f"{code}: content changed but version is still {current['version']}; "
            "bump it and run `python -m tests.test_scenario_versions`"
        )


if __name__ == "__main__":
    FINGERPRINTS.write_text(json.dumps(fingerprints(), indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {FINGERPRINTS}")
