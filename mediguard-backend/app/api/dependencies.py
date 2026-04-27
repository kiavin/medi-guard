from fastapi import Depends, HTTPException, status, Query as FastAPIQuery
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, Query
from sqlalchemy import or_, asc, desc
import jwt
from typing import Optional, Any, Type, List
from app.core.security import SECRET_KEY, ALGORITHM
from app.core.database import SessionLocal
from app.models.user import User
from app.models.user import TokenBlocklist

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # 1. Check if the token was logged out!
    is_blacklisted = db.query(TokenBlocklist).filter(TokenBlocklist.token == token).first()
    if is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    if current_user.is_locked:
        raise HTTPException(status_code=403, detail="Account is locked. Please contact IT.")
    return current_user

# RBAC: Dependency to check roles
class RoleChecker:
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_active_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(status_code=403, detail="Operation not permitted for your role")
        return user

# Global Pagination, Search, and Sorting
class QueryParams:
    def __init__(
        self,
        page: int = FastAPIQuery(1, ge=1),
        size: int = FastAPIQuery(20, ge=1, le=100, alias="per-page"),
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        order: str = FastAPIQuery("desc", pattern="^(asc|desc)$")
    ):
        self.page = page
        self.size = size
        self.search = search
        self.sort_by = sort_by
        self.sort_desc = order == "desc"

def apply_filters_and_paginate(
    query: Query,
    model: Type[Any],
    params: QueryParams,
    search_columns: List[str] = None
) -> dict:
    """
    Applies SQLAlchemy ilike() filtering, dynamic sorting, and pagination.
    Returns a dictionary with 'items' and 'meta'.
    """
    # 1. Search Filtering
    if params.search and search_columns:
        search_filters = []
        for col_name in search_columns:
            column = getattr(model, col_name, None)
            if column is not None:
                search_filters.append(column.ilike(f"%{params.search}%"))
        
        if search_filters:
            query = query.filter(or_(*search_filters))

    # 2. Total Count (before pagination)
    total_items = query.count()

    # 3. Dynamic Sorting
    if params.sort_by:
        sort_column = getattr(model, params.sort_by, None)
        if sort_column is not None:
            order_func = desc if params.sort_desc else asc
            query = query.order_by(order_func(sort_column))
    else:
        # Default sort by created_at desc if it exists
        if hasattr(model, "created_at"):
            query = query.order_by(desc(model.created_at))

    # 4. Pagination
    offset = (params.page - 1) * params.size
    items = query.offset(offset).limit(params.size).all()

    # 5. Build Metadata
    total_pages = (total_items + params.size - 1) // params.size if total_items > 0 else 0

    return {
        "items": items,
        "meta": {
            "total": total_items,
            "page": params.page,
            "size": params.size,
            "pages": total_pages
        }
    }
