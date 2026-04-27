from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.api.dependencies import get_db, get_current_active_user, RoleChecker
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.base_response import APIResponse, send_success

router = APIRouter(
    prefix="/users",
    tags=["User Management"],
    dependencies=[Depends(get_current_active_user)]
)

# Admin Only Dependency
allow_admin = RoleChecker(["admin"])

@router.get("/me", response_model=APIResponse[UserResponse])
def read_user_me(current_user: User = Depends(get_current_active_user)):
    return send_success(data=current_user)

@router.get("/", response_model=APIResponse[List[UserResponse]])
def read_all_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(allow_admin)
):
    users = db.query(User).offset(skip).limit(limit).all()
    return send_success(data=users)

@router.get("/{user_id}", response_model=APIResponse[UserResponse])
def read_user_by_id(
    user_id: str, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(allow_admin)
):
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
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_in.model_dump(exclude_unset=True)
    
    # Auto-sync security fields if the admin changes the UI 'status' string
    if "status" in update_data:
        if update_data["status"] in ["suspended", "disabled"]:
            user.is_active = False
        elif update_data["status"] == "active":
            user.is_active = True

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
    current_admin: User = Depends(allow_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    # Restore access and sync the UI status
    user.status = "active"
    user.is_active = True
    user.is_locked = False
    user.locked_until = None
    user.failed_login_attempts = 0
    
    db.commit()
    db.refresh(user)
    
    return send_success(
        data=user,
        message=f"Staff account for {user.first_name or user.username} has been fully restored and unlocked.",
        theme="success",
        alert_type="toast"
    )

# --- NEW: Quick Suspend Route ---
@router.put("/{user_id}/disable", response_model=APIResponse[UserResponse])
def disable_user(
    user_id: str, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(allow_admin)
):
    """
    Instantly revokes login access and marks the account as disabled.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    # Disable the user
    user.status = "disabled"
    user.is_active = False
    
    db.commit()
    db.refresh(user)
    
    return send_success(
        data=user,
        message=f"Staff account for {user.first_name or user.username} has been disabled.",
        theme="danger",
        alert_type="toast"
    )