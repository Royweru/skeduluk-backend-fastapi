# app/routers/users.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from .. import auth, schemas, models
from ..database import get_async_db
from ..utils.security import verify_password, get_password_hash
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


@router.put("/change-password")
async def change_password(
    password_data: schemas.ChangePasswordRequest,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Change user password.
    Requires current password verification.
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Check if new password is different from current
    if verify_password(password_data.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )

    # Update password
    current_user.hashed_password = get_password_hash(
        password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    await db.commit()

    return {"message": "Password updated successfully! 🔐"}


@router.put("/notification-preferences", response_model=schemas.UserResponse)
async def update_notification_preferences(
    prefs: schemas.NotificationPreferencesUpdate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Update user email notification preferences."""
    if prefs.email_on_post_success is not None:
        current_user.email_on_post_success = prefs.email_on_post_success
    if prefs.email_on_post_failure is not None:
        current_user.email_on_post_failure = prefs.email_on_post_failure
    if prefs.email_weekly_analytics is not None:
        current_user.email_weekly_analytics = prefs.email_weekly_analytics

    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.get("/stats", response_model=schemas.UserStatsResponse)
async def get_user_stats(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get user statistics for profile page."""
    # Count posts by status
    total_posts_result = await db.execute(
        select(func.count(models.Post.id)).where(
            models.Post.user_id == current_user.id
        )
    )
    total_posts = total_posts_result.scalar() or 0

    posted_result = await db.execute(
        select(func.count(models.Post.id)).where(
            models.Post.user_id == current_user.id,
            models.Post.status.in_(['posted', 'partial'])
        )
    )
    posts_published = posted_result.scalar() or 0

    scheduled_result = await db.execute(
        select(func.count(models.Post.id)).where(
            models.Post.user_id == current_user.id,
            models.Post.status == 'scheduled'
        )
    )
    posts_scheduled = scheduled_result.scalar() or 0

    failed_result = await db.execute(
        select(func.count(models.Post.id)).where(
            models.Post.user_id == current_user.id,
            models.Post.status == 'failed'
        )
    )
    posts_failed = failed_result.scalar() or 0

    # Count connected platforms
    connections_result = await db.execute(
        select(func.count(models.SocialConnection.id)).where(
            models.SocialConnection.user_id == current_user.id,
            models.SocialConnection.is_active == True
        )
    )
    connected_platforms = connections_result.scalar() or 0

    # Calculate total engagement from analytics
    engagement_result = await db.execute(
        select(
            func.coalesce(func.sum(models.PostAnalytics.likes), 0) +
            func.coalesce(func.sum(models.PostAnalytics.comments), 0) +
            func.coalesce(func.sum(models.PostAnalytics.shares), 0)
        ).select_from(models.PostAnalytics).join(
            models.Post, models.Post.id == models.PostAnalytics.post_id
        ).where(models.Post.user_id == current_user.id)
    )
    total_engagement = engagement_result.scalar() or 0

    # Calculate member since days
    member_since_days = 0
    if current_user.created_at:
        member_since_days = (datetime.utcnow() - current_user.created_at).days

    return schemas.UserStatsResponse(
        total_posts=total_posts,
        posts_published=posts_published,
        posts_scheduled=posts_scheduled,
        posts_failed=posts_failed,
        connected_platforms=connected_platforms,
        total_engagement=int(total_engagement),
        member_since_days=member_since_days
    )


@router.post("/deactivate")
async def deactivate_account(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Deactivate user account.
    Account can be reactivated by contacting support.
    """
    current_user.is_active = False
    current_user.updated_at = datetime.utcnow()
    await db.commit()

    return {"message": "Account deactivated. Contact support to reactivate."}


@router.delete("/me")
async def delete_account(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Permanently delete user account and all associated data.
    This action cannot be undone.
    """
    await db.delete(current_user)
    await db.commit()

    return {"message": "Account permanently deleted. We're sad to see you go! 👋"}
