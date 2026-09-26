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
    rule = RuleDefinition.model_validate({"field": field, "operator": operator, "value": value})

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
    not_matching = RuleDefinition(field="has_registration", operator=RuleOperator.EQ, value=True)

    assert not evaluate_all([matching, not_matching], context)


def test_empty_rules_match(context: UserContext) -> None:
    assert evaluate_all([], context)


def unchecked(field: str, operator: RuleOperator, value: object) -> RuleDefinition:
    """Build a rule bypassing validation to test evaluator strictness directly."""
    return RuleDefinition.model_construct(field=field, operator=operator, value=value)


def test_eq_does_not_coerce_types(context: UserContext) -> None:
    assert not evaluate(unchecked("age", RuleOperator.EQ, "18"), context)
    assert not evaluate(unchecked("has_registration", RuleOperator.EQ, 0), context)


def test_ne_does_not_coerce_types(context: UserContext) -> None:
    assert evaluate(unchecked("age", RuleOperator.NE, "18"), context)


def test_ordered_comparison_rejects_incompatible_types(context: UserContext) -> None:
    with pytest.raises(ValueError, match="Cannot compare int with str"):
        evaluate(unchecked("age", RuleOperator.GT, "17"), context)


@pytest.mark.parametrize(
    ("field", "operator", "value", "message"),
    [
        ("age", RuleOperator.GT, "17", "expects int"),
        ("age", RuleOperator.EQ, True, "expects int"),
        ("has_registration", RuleOperator.EQ, 0, "expects bool"),
        ("region_code", RuleOperator.EQ, 77, "expects str"),
        ("region_code", RuleOperator.GT, "77", "only supported for numeric"),
        ("housing_type", RuleOperator.EQ, "HOSTEL", "Unknown value"),
        ("region_code", RuleOperator.EQ, ["77"], "requires a scalar"),
    ],
)
def test_rule_value_type_is_validated(
    field: str, operator: RuleOperator, value: object, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        RuleDefinition.model_validate({"field": field, "operator": operator, "value": value})


@pytest.mark.parametrize("operator", [RuleOperator.IN, RuleOperator.NOT_IN])
def test_membership_operator_requires_array(operator: RuleOperator) -> None:
    with pytest.raises(ValidationError, match="requires an array value"):
        RuleDefinition(field="region_code", operator=operator, value="77")


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RuleDefinition.model_validate(
            {"field": "unknown", "operator": RuleOperator.EQ, "value": True}
        )
