from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.api.dependencies import get_db, get_current_active_user, RoleChecker
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.base_response import APIResponse, send_success

router = APIRouter(prefix="/users", tags=["User Management"])

# Admin Only Dependency
allow_admin = RoleChecker(["admin"])

@router.get("/me", response_model=APIResponse[UserResponse])
def read_user_me(current_user: User = Depends(get_current_active_user)):
    """
    Get the profile of the currently logged-in user.
    Any active user (admin, clinician, etc.) can use this.
    """
    return send_success(data=current_user)

@router.get("/", response_model=APIResponse[List[UserResponse]])
def read_all_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(allow_admin)
):
    """
    List all users in the system. (Admins only)
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return send_success(data=users)

@router.get("/{user_id}", response_model=APIResponse[UserResponse])
def read_user_by_id(
    user_id: str, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(allow_admin)
):
    """
    Get a specific user's details by their ID. (Admins only)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return send_success(data=user)

@router.put("/{user_id}", response_model=APIResponse[UserResponse])
def update_user(
    user_id: str, 
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(allow_admin)
):
    """
    Update a user's role, active status, or lock status. (Admins only)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update only the fields that were provided in the request
    update_data = user_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
        
    db.commit()
    db.refresh(user)
    
    return send_success(
        data=user,
        message=f"User {user.username} updated successfully.",
        theme="success",
        alert_type="toast"
    )

@router.put("/{user_id}/enable", response_model=APIResponse[UserResponse])
def enable_user(
    user_id: str, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(allow_admin) # Admin only!
):
    """
    Re-enables a disabled staff account and completely clears any 
    failed login attempts or temporary security locks.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    # Restore access and wipe all penalty flags
    user.is_active = True
    user.is_locked = False
    user.locked_until = None
    user.failed_login_attempts = 0
    
    db.commit()
    db.refresh(user)
    
    return send_success(
        data=user,
        message=f"Staff account for {user.username} has been fully restored and unlocked.",
        theme="success",
        alert_type="toast"
    )