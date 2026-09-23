from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ScenarioNotFoundError
from app.rules.engine import evaluate_all
from app.rules.schemas import RuleDefinition
from app.scenarios.models import Scenario
from app.scenarios.repository import ScenarioRepository
from app.scenarios.schemas import ScenarioDefinition, ScenarioStepDefinition
from app.users.schemas import UserContext


class ScenarioService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ScenarioRepository(session)

    async def get_for(self, context: UserContext) -> Scenario:
        """Pick the active scenario whose audience rules match the user."""
        for scenario in await self.repository.list_active():
            audience = [RuleDefinition.model_validate(rule) for rule in scenario.audience]
            if evaluate_all(audience, context):
                return scenario
        raise ScenarioNotFoundError

    def to_definition(self, scenario: Scenario) -> ScenarioDefinition:
        return ScenarioDefinition(
            code=scenario.code,
            title=scenario.title,
            description=scenario.description,
            version=scenario.version,
            is_active=scenario.is_active,
            audience=[RuleDefinition.model_validate(rule) for rule in scenario.audience],
            steps=[
                ScenarioStepDefinition(
                    code=step.code,
                    title=step.title,
                    short_description=step.short_description,
                    full_description=step.full_description,
                    reason=step.reason,
                    location=step.location,
                    recommended_days=step.recommended_days,
                    position=step.position,
                    category=step.category,
                    estimated_duration=step.estimated_duration,
                    is_required=step.is_required,
                    rules=[
                        RuleDefinition.model_validate(
                            {
                                "field": rule.field,
                                "operator": rule.operator,
                                "value": rule.value,
                            }
                        )
                        for rule in step.rules
                    ],
                )
                for step in scenario.steps
            ],
        )

