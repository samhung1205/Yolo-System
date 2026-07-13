"""
Users API routes (admin only):
  GET    /api/users
  POST   /api/users
  PUT    /api/users/{id}
  DELETE /api/users/{id}
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import user_service
from app.services.user_response_service import to_user_read

router = APIRouter()


@router.get("", response_model=dict)
def list_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None),
):
    """List all users with pagination and optional search. Admin only."""
    result = user_service.list_users(db, page=page, limit=limit, search=search)
    result["items"] = [to_user_read(u) for u in result["items"]]
    return result


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
):
    """Admin creates a new user account."""
    user = user_service.create_user_by_admin(db, user_in)
    return to_user_read(user)


@router.put("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
):
    """Admin updates a user's information."""
    user = user_service.update_user(db, user_id, user_in)
    return to_user_read(user)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
):
    """Admin deletes a user."""
    user_service.delete_user(db, user_id)
    return {"message": "User deleted successfully"}
