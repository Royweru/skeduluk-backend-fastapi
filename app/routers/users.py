# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth, schemas, models
from ..database import get_async_db
from app.crud.user_crud import UserCRUD

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """Get current user information"""
    return current_user

@router.put("/me", response_model=schemas.UserResponse)
async def update_current_user(
    user_update: schemas.UserUpdate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Update current user information"""
    user = await UserCRUD.update_user(db, current_user.id, user_update)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user