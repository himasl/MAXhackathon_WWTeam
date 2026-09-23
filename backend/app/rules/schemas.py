from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.scenarios.models import RuleOperator
from app.users.models import EducationType, HousingType

type RuleField = Literal[
    "age",
    "region_code",
    "education_type",
    "housing_type",
    "has_registration",
    "has_clinic_attachment",
]
type RuleScalar = StrictStr | StrictInt | StrictFloat | StrictBool
type RuleValue = RuleScalar | list[RuleScalar]

ORDERED_OPERATORS = {RuleOperator.GT, RuleOperator.GTE, RuleOperator.LT, RuleOperator.LTE}
MEMBERSHIP_OPERATORS = {RuleOperator.IN, RuleOperator.NOT_IN}

# Expected value type for each context field. Enum fields list their allowed values.
FIELD_TYPES: dict[str, type] = {
    "age": int,
    "region_code": str,
    "education_type": str,
    "housing_type": str,
    "has_registration": bool,
    "has_clinic_attachment": bool,
}
ENUM_VALUES: dict[str, set[str]] = {
    "education_type": {item.value for item in EducationType},
    "housing_type": {item.value for item in HousingType},
}


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: RuleField
    operator: RuleOperator
    value: RuleValue

    @model_validator(mode="after")
    def validate_operator_value(self) -> Self:
        if self.operator in MEMBERSHIP_OPERATORS and not isinstance(self.value, list):
            raise ValueError(f"{self.operator.value} requires an array value")
        if self.operator not in MEMBERSHIP_OPERATORS and isinstance(self.value, list):
            raise ValueError(f"{self.operator.value} requires a scalar value")
        if self.operator in ORDERED_OPERATORS and FIELD_TYPES[self.field] is not int:
            raise ValueError(f"{self.operator.value} is only supported for numeric fields")

        values = self.value if isinstance(self.value, list) else [self.value]
        expected = FIELD_TYPES[self.field]
        for item in values:
            if type(item) is not expected:
                raise ValueError(
                    f"Field {self.field} expects {expected.__name__}, got {type(item).__name__}"
                )
            allowed = ENUM_VALUES.get(self.field)
            if allowed is not None and item not in allowed:
                raise ValueError(f"Unknown value {item!r} for field {self.field}")
        return self
