from app.routes.schemas import GeneratedRoute
from app.rules.engine import evaluate_all
from app.scenarios.schemas import ScenarioDefinition
from app.users.schemas import UserContext


class RouteGenerator:
    def generate(self, context: UserContext, scenario: ScenarioDefinition) -> GeneratedRoute:
        steps = [step for step in scenario.steps if evaluate_all(step.rules, context)]
        steps.sort(key=lambda step: step.position)
        return GeneratedRoute(
            scenario_code=scenario.code,
            scenario_version=scenario.version,
            steps=steps,
        )

