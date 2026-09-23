from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ScenarioNotFoundError
from app.rules.schemas import RuleDefinition
from app.scenarios.models import Scenario
from app.scenarios.repository import ScenarioRepository
from app.scenarios.schemas import ScenarioDefinition, ScenarioStepDefinition


class ScenarioService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ScenarioRepository(session)

    async def get_active(self) -> Scenario:
        scenario = await self.repository.get_active()
        if scenario is None:
            raise ScenarioNotFoundError
        return scenario

    def to_definition(self, scenario: Scenario) -> ScenarioDefinition:
        return ScenarioDefinition(
            code=scenario.code,
            title=scenario.title,
            description=scenario.description,
            version=scenario.version,
            is_active=scenario.is_active,
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

