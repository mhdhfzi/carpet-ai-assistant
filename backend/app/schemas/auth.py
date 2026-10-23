from pydantic import BaseModel, ConfigDict, Field

from app.db.models import OwnerRole


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)
    remember: bool = False  # "Ingat saya": a long-lived token for the user's own phone


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class OwnerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: OwnerRole
