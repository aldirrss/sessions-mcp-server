from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class TokenCreateInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Token name, e.g. 'VSCode laptop'")
    expires_days: Optional[int] = Field(None, ge=1, le=3650, description="Days until expiry. Omit for no expiry.")


class TokenRevokeInput(BaseModel):
    token_id: str = Field(..., description="UUID of the token to revoke")


class UserSetRoleInput(BaseModel):
    user_id: str = Field(..., description="UUID of the user")
    role: str = Field(..., pattern="^(user|admin)$", description="'user' or 'admin'")


class UserSetActiveInput(BaseModel):
    user_id: str = Field(..., description="UUID of the user")
    active: bool = Field(..., description="True to activate, False to deactivate")


class UserGetInput(BaseModel):
    user_id: Optional[str] = Field(None, description="UUID. Omit to get current authenticated user.")
