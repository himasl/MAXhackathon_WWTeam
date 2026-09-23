from app.rules.schemas import RuleDefinition
from app.scenarios.engine import RouteGenerator
from app.scenarios.models import RuleOperator, StepCategory
from app.scenarios.schemas import ScenarioDefinition, ScenarioStepDefinition
from app.users.models import EducationType, HousingType
from app.users.schemas import UserContext


def context() -> UserContext:
    return UserContext(
        age=18,
        region_code="77",
        education_type=EducationType.FULL_TIME,
        housing_type=HousingType.DORMITORY,
        has_registration=False,
        has_clinic_attachment=False,
    )


def step(
    code: str,
    position: int,
    rules: list[RuleDefinition] | None = None,
) -> ScenarioStepDefinition:
    return ScenarioStepDefinition(
        code=code,
        title=code,
        position=position,
        category=StepCategory.OTHER,
        rules=rules or [],
    )


def test_generate_route_filters_steps_and_preserves_position() -> None:
    scenario = ScenarioDefinition(
        code="student_relocation_v1",
        version=1,
        steps=[
            step(
                "clinic_already_attached",
                30,
                [
                    RuleDefinition(
                        field="has_clinic_attachment",
                        operator=RuleOperator.EQ,
                        value=True,
                    )
                ],
            ),
            step("always_applicable", 20),
            step(
                "temporary_registration",
                10,
                [
                    RuleDefinition(
                        field="has_registration",
                        operator=RuleOperator.EQ,
                        value=False,
                    ),
                    RuleDefinition(
                        field="age",
                        operator=RuleOperator.GTE,
                        value=18,
                    ),
                ],
            ),
        ],
    )

    route = RouteGenerator().generate(context(), scenario)

    assert route.scenario_code == "student_relocation_v1"
    assert route.scenario_version == 1
    assert [item.code for item in route.steps] == [
        "temporary_registration",
        "always_applicable",
    ]
    assert [item.position for item in route.steps] == [10, 20]


def test_step_is_excluded_when_one_of_multiple_rules_fails() -> None:
    scenario = ScenarioDefinition(
        code="student_relocation_v1",
        version=1,
        steps=[
            step(
                "not_applicable",
                1,
                [
                    RuleDefinition(field="age", operator=RuleOperator.GTE, value=18),
                    RuleDefinition(
                        field="education_type",
                        operator=RuleOperator.EQ,
                        value="PART_TIME",
                    ),
                ],
            )
        ],
    )

    route = RouteGenerator().generate(context(), scenario)

    assert route.steps == []

