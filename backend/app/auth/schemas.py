from pydantic import BaseModel, ConfigDict, Field

from app.users.schemas import CurrentUserResponse


class MaxAuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    init_data: str = Field(min_length=1, max_length=8192)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    start_param: str | None
    user: CurrentUserResponse
