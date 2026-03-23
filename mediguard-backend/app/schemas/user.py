from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "clinician"

class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_locked: Optional[bool] = None

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    is_locked: bool
    email_verified: bool

    class Config:
        from_attributes = True