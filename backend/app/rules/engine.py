from collections.abc import Iterable

from app.rules.evaluator import evaluate
from app.rules.schemas import RuleDefinition
from app.users.schemas import UserContext


def evaluate_all(rules: Iterable[RuleDefinition], context: UserContext) -> bool:
    return all(evaluate(rule, context) for rule in rules)

