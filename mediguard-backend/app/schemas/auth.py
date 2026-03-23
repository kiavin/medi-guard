from pydantic import BaseModel, EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str # <-- Added this
    token_type: str = "Bearer"
    expires_in: int    

class LoginRequest(BaseModel):
    username: str
    password: str