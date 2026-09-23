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


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: RuleField
    operator: RuleOperator
    value: RuleValue

    @model_validator(mode="after")
    def validate_operator_value(self) -> Self:
        if self.operator in {RuleOperator.IN, RuleOperator.NOT_IN} and not isinstance(
            self.value, list
        ):
            raise ValueError(f"{self.operator.value} requires an array value")
        return self
