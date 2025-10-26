# app/routers/social.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from .. import models, auth
from ..database import get_async_db
from ..services.oauth_service import OAuthService

router = APIRouter(prefix="/social", tags=["social"])


@router.get("/connections")
async def get_connections(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get user's connected social accounts"""
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.user_id == current_user.id,
            models.SocialConnection.is_active == True
        )
    )
    connections = result.scalars().all()
    
    return {
        "connections": [
            {
                "id": conn.id,
                "platform": conn.platform,
                "platform_user_id": conn.platform_user_id,
                "platform_username": conn.platform_username,
                "username": conn.username,
                "is_active": conn.is_active,
                "last_synced": conn.last_synced.isoformat() if conn.last_synced else None,
                "created_at": conn.created_at.isoformat() if conn.created_at else None
            }
            for conn in connections
        ]
    }


@router.delete("/connections/{connection_id}")
async def disconnect_platform(
    connection_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Disconnect a social platform"""
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.id == connection_id,
            models.SocialConnection.user_id == current_user.id
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Mark as inactive instead of deleting (soft delete)
    connection.is_active = False
    await db.commit()
    
    return {
        "message": f"{connection.platform} disconnected successfully",
        "platform": connection.platform
    }


@router.post("/connections/{connection_id}/refresh")
async def refresh_token(
    connection_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Refresh access token for a connection"""
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.id == connection_id,
            models.SocialConnection.user_id == current_user.id
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    success = await OAuthService.refresh_access_token(db, connection_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to refresh token")
    
    return {"message": "Token refreshed successfully"}