import os
from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt

# Get these from your .env file
SECRET_KEY = os.getenv("JWT_SECRET", "bcshbdihidbuhiubiduwbue2u0u0jeu08iu3h98eh9uewh9o8uhwecew9898")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480 # 8 hours per your requirements

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Function to generate tokens for email verification / password reset
def create_action_token(email: str, action: str, expires_minutes: int = 60):
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    return jwt.encode({"sub": email, "action": action, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)