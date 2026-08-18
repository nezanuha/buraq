
from pydantic import BaseModel


class ProfileRead(BaseModel):
    id: int
    user_id: int
    bio: str
    avatar_url: str

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    bio: str | None = None
    avatar_url: str | None = None
