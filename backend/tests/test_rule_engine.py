import pytest
from pydantic import ValidationError

from app.rules.engine import evaluate_all
from app.rules.evaluator import evaluate
from app.rules.schemas import RuleDefinition
from app.scenarios.models import RuleOperator
from app.users.models import EducationType, HousingType
from app.users.schemas import UserContext


@pytest.fixture
def context() -> UserContext:
    return UserContext(
        age=18,
        region_code="77",
        education_type=EducationType.FULL_TIME,
        housing_type=HousingType.DORMITORY,
        has_registration=False,
        has_clinic_attachment=True,
    )


@pytest.mark.parametrize(
    ("field", "operator", "value"),
    [
        ("age", RuleOperator.EQ, 18),
        ("age", RuleOperator.NE, 17),
        ("age", RuleOperator.GT, 17),
        ("age", RuleOperator.GTE, 18),
        ("age", RuleOperator.LT, 19),
        ("age", RuleOperator.LTE, 18),
        ("region_code", RuleOperator.IN, ["77", "78", "16"]),
        ("region_code", RuleOperator.NOT_IN, ["78", "16"]),
    ],
)
def test_each_operator(
    context: UserContext,
    field: str,
    operator: RuleOperator,
    value: object,
) -> None:
    rule = RuleDefinition.model_validate(
        {"field": field, "operator": operator, "value": value}
    )

    assert evaluate(rule, context)


def test_boolean_value(context: UserContext) -> None:
    rule = RuleDefinition(
        field="has_registration",
        operator=RuleOperator.EQ,
        value=False,
    )

    assert evaluate(rule, context)


def test_numeric_value(context: UserContext) -> None:
    rule = RuleDefinition(field="age", operator=RuleOperator.GTE, value=18)

    assert evaluate(rule, context)


def test_enum_context_matches_string_value(context: UserContext) -> None:
    rule = RuleDefinition(
        field="education_type",
        operator=RuleOperator.EQ,
        value="FULL_TIME",
    )

    assert evaluate(rule, context)


def test_array_value(context: UserContext) -> None:
    rule = RuleDefinition(
        field="housing_type",
        operator=RuleOperator.IN,
        value=["DORMITORY", "RENT"],
    )

    assert evaluate(rule, context)


def test_multiple_rules_use_and(context: UserContext) -> None:
    matching = RuleDefinition(field="age", operator=RuleOperator.GTE, value=18)
    not_matching = RuleDefinition(
        field="has_registration", operator=RuleOperator.EQ, value=True
    )

    assert not evaluate_all([matching, not_matching], context)


def test_empty_rules_match(context: UserContext) -> None:
    assert evaluate_all([], context)


def test_eq_does_not_coerce_types(context: UserContext) -> None:
    numeric_string = RuleDefinition(field="age", operator=RuleOperator.EQ, value="18")
    bool_as_integer = RuleDefinition(
        field="has_registration", operator=RuleOperator.EQ, value=0
    )

    assert not evaluate(numeric_string, context)
    assert not evaluate(bool_as_integer, context)


def test_ne_does_not_coerce_types(context: UserContext) -> None:
    rule = RuleDefinition(field="age", operator=RuleOperator.NE, value="18")

    assert evaluate(rule, context)


def test_ordered_comparison_rejects_incompatible_types(context: UserContext) -> None:
    rule = RuleDefinition(field="age", operator=RuleOperator.GT, value="17")

    with pytest.raises(ValueError, match="Cannot compare int with str"):
        evaluate(rule, context)


@pytest.mark.parametrize("operator", [RuleOperator.IN, RuleOperator.NOT_IN])
def test_membership_operator_requires_array(operator: RuleOperator) -> None:
    with pytest.raises(ValidationError, match="requires an array value"):
        RuleDefinition(field="region_code", operator=operator, value="77")


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RuleDefinition.model_validate(
            {"field": "unknown", "operator": RuleOperator.EQ, "value": True}
        )

