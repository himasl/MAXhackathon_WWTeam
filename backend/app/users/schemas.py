from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr

from app.users.models import EducationType, HousingType


class ProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: StrictInt
    region_code: StrictStr
    education_type: EducationType
    housing_type: HousingType
    has_registration: StrictBool
    has_clinic_attachment: StrictBool


class ProfileResponse(ProfilePayload):
    pass


class CurrentUserResponse(BaseModel):
    id: UUID
    max_user_id: int


class UserContext(ProfilePayload):

    def rule_value(self, field: str) -> object:
        return self.model_dump(mode="json")[field]

