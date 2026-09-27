from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from app.users.models import Citizenship, EducationType, HousingType


class ProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: StrictInt = Field(ge=14, le=100)
    region_code: StrictStr
    education_type: EducationType
    housing_type: HousingType
    has_registration: StrictBool
    has_clinic_attachment: StrictBool
    citizenship: Citizenship = Citizenship.RU
    university_code: StrictStr | None = Field(default=None, max_length=50)


class ProfileResponse(ProfilePayload):
    # Stored profiles are returned as they are; the 14–100 bound applies to input only.
    age: StrictInt


class CurrentUserResponse(BaseModel):
    id: UUID
    max_user_id: int


class UserContext(ProfilePayload):
    age: StrictInt

    def rule_value(self, field: str) -> object:
        return self.model_dump(mode="json")[field]

