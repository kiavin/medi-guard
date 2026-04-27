from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from pydantic import BaseModel

from app.api.dependencies import get_db, get_current_active_user, RoleChecker
from app.core.security import verify_password, get_password_hash, create_access_token, create_action_token, SECRET_KEY, ALGORITHM
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.schemas.auth import Token, PasswordResetRequest, PasswordResetConfirm, LoginRequest, RefreshTokenRequest
from app.schemas.base_response import APIResponse, send_success
from app.models.user import TokenBlocklist

router = APIRouter(prefix="/auth", tags=["Authentication"])

MAX_LOGIN_ATTEMPTS = 5

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

@router.post("/register", response_model=APIResponse[UserResponse])
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """Registers a new user (You might want to restrict this to Admins later)"""
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=422, detail="Email already registered")
    
    new_user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role=user_in.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # TODO: Trigger background task to send verification email here
    return send_success(
        data=new_user,
        message="Account successfully created.",
        theme="success",
        alert_type="toast"
    )

@router.post("/login", response_model=APIResponse[Token])
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == login_data.username).first()
    
    if not user:
        # Target the password field directly
        raise HTTPException(status_code=422, detail={"password": "Incorrect username or password."})

    # Check if locked
    if user.is_locked:
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise HTTPException(
                status_code=403, 
                detail={"password": f"Account locked due to too many failed attempts. Try again later."}
            )
        else:
            # Lock has expired, unlock the user
            user.is_locked = False
            user.failed_login_attempts = 0
            db.commit()

    if not verify_password(login_data.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.is_locked = True
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db.commit()
        # Target the password field directly
        raise HTTPException(status_code=422, detail={"password": "Incorrect username or password."})

    # Successful login: reset attempts
    user.failed_login_attempts = 0
    db.commit()

    # 1. Create a SHORT-LIVED Access Token (30 mins)
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(data={"sub": user.id, "role": user.role}, expires_delta=access_token_expires)
    
    # 2. Create a LONG-LIVED Refresh Token (7 days)
    refresh_token_expires = timedelta(days=7)
    refresh_token = create_access_token(data={"sub": user.id, "type": "refresh"}, expires_delta=refresh_token_expires)
    
    token_data = {
        "access_token": access_token, 
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": 1 * 60 # 5 minutes in seconds
    }
    
    return send_success(data=token_data,
                        message="Access granted",
                        theme="success",
                        alert_type="toast")

@router.post("/refresh", response_model=APIResponse[Token])
def refresh_access_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Use a valid refresh_token to get a new access_token without logging in again."""
    try:
        # Decode the refresh token
        refresh_token = payload.refresh_token
        payload_data = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Verify it's actually a refresh token
        if payload_data.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
            
        user_id: str = payload_data.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
            
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Get user to ensure they still exist and aren't locked
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active or user.is_locked:
        raise HTTPException(status_code=401, detail="User account is disabled or locked")

    # Generate a new short-lived access token
    access_token_expires = timedelta(minutes=30)
    new_access_token = create_access_token(data={"sub": user.id, "role": user.role}, expires_delta=access_token_expires)
    
    token_data = {
        "access_token": new_access_token, 
        "refresh_token": refresh_token, # Send back the same refresh token
        "token_type": "Bearer",
        "expires_in": 30 * 60
    }
    
    return send_success(data=token_data)

@router.post("/logout", response_model=APIResponse[dict])
def logout(
    token: str = Depends(oauth2_scheme), # <-- This strictly reads the 'Authorization' header! No body needed.
    db: Session = Depends(get_db)
):
    """
    True backend logout. Extracts the access token directly from the 
    Authorization header and adds it to the blocklist.
    """
    # Check if it's already blocklisted (idempotent)
    already_blocked = db.query(TokenBlocklist).filter(TokenBlocklist.token == token).first()
    
    if not already_blocked:
        blocked_token = TokenBlocklist(token=token)
        db.add(blocked_token)
        db.commit()
        
    return send_success(
        data={"status": "logged_out"}, 
        message="Successfully logged out.", 
        theme="info", 
        alert_type="toast" 
    )

@router.post("/request-password-reset", response_model=APIResponse[Dict[str, Any]])
def request_password_reset(request: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if user:
        reset_token = create_action_token(email=user.email, action="reset_password", expires_minutes=15)
        # TODO: Send email with reset_token
        print(f"Mock Email: Reset link -> http://yourfrontend.com/reset-password?token={reset_token}")
    
    # Always return 200 to prevent email enumeration attacks
    return send_success(
        data={"status": "processed"},
        message="If that email exists, a reset link has been sent.",
        theme="info",
        alert_type="alert"
    )

@router.post("/reset-password", response_model=APIResponse[Dict[str, Any]])
def reset_password(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    try:
        decoded = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM])
        if decoded.get("action") != "reset_password":
            raise HTTPException(status_code=422, detail="Invalid token type")
        
        user = db.query(User).filter(User.email == decoded.get("sub")).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        user.password_hash = get_password_hash(payload.new_password)
        db.commit()
        
        return send_success(
            data={"status": "success"},
            message="Password successfully reset",
            theme="success",
            alert_type="toast"
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=422, detail="Invalid or expired token")

# Example of an Admin-Only route
allow_admin = RoleChecker(["admin"])

@router.post("/admin/lock-account/{user_id}", response_model=APIResponse[Dict[str, Any]])
def lock_user_account(user_id: str, db: Session = Depends(get_db), current_admin: User = Depends(allow_admin)):
    """Explicitly lock an account manually. Only Admins can do this."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.is_locked = True
    user.locked_until = datetime.utcnow() + timedelta(days=365) # Lock indefinitely
    db.commit()
    
    return send_success(
        data={"status": "locked"},
        message=f"User {user.username} has been locked.",
        theme="warning",
        alert_type="alert"
    )