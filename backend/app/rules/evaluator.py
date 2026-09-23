import operator
from collections.abc import Callable
from typing import Any

from app.rules.schemas import RuleDefinition
from app.scenarios.models import RuleOperator
from app.users.schemas import UserContext

Comparison = Callable[[Any, Any], bool]


def _strict_equal(left: object, right: object) -> bool:
    return type(left) is type(right) and left == right


def _ordered_compare(left: object, right: object, operation: Comparison) -> bool:
    numeric = (int, float)
    both_numeric = (
        type(left) in numeric
        and type(right) in numeric
        and not isinstance(left, bool)
        and not isinstance(right, bool)
    )
    if type(left) is not type(right) and not both_numeric:
        raise ValueError(
            f"Cannot compare {type(left).__name__} with {type(right).__name__}"
        )

    try:
        return operation(left, right)
    except TypeError as error:
        raise ValueError(
            f"Cannot compare {type(left).__name__} with {type(right).__name__}"
        ) from error


def _contains(value: object, candidates: object) -> bool:
    if not isinstance(candidates, list):
        raise TypeError("IN and NOT_IN require an array value")
    return any(_strict_equal(value, candidate) for candidate in candidates)


def evaluate(rule: RuleDefinition, context: UserContext) -> bool:
    current = context.rule_value(rule.field)

    operations: dict[RuleOperator, Comparison] = {
        RuleOperator.EQ: _strict_equal,
        RuleOperator.NE: lambda left, right: not _strict_equal(left, right),
        RuleOperator.GT: lambda left, right: _ordered_compare(left, right, operator.gt),
        RuleOperator.GTE: lambda left, right: _ordered_compare(left, right, operator.ge),
        RuleOperator.LT: lambda left, right: _ordered_compare(left, right, operator.lt),
        RuleOperator.LTE: lambda left, right: _ordered_compare(left, right, operator.le),
        RuleOperator.IN: _contains,
        RuleOperator.NOT_IN: lambda left, right: not _contains(left, right),
    }
    return operations[rule.operator](current, rule.value)
