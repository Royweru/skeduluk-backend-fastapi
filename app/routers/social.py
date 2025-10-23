# app/routers/social.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth, schemas, models
from ..database import get_async_db
from ..crud import SocialConnectionCRUD

router = APIRouter(prefix="/social", tags=["social"])

@router.get("/connections", response_model=list[schemas.SocialConnectionResponse])
async def get_connections(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get user's social connections"""
    connections = await SocialConnectionCRUD.get_connections_by_user(db, current_user.id)
    return connections

@router.delete("/connections/{connection_id}")
async def disconnect_account(
    connection_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Disconnect a social account"""
    success = await SocialConnectionCRUD.deactivate_connection(db, connection_id, current_user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    return {"message": "Successfully disconnected account"}

@router.get("/platforms")
async def get_supported_platforms():
    """Get list of supported social platforms"""
    return {
        "platforms": [
            {"name": "Twitter/X", "key": "TWITTER", "supported": True},
            {"name": "Facebook", "key": "FACEBOOK", "supported": True},
            {"name": "LinkedIn", "key": "LINKEDIN", "supported": True},
            {"name": "Instagram", "key": "INSTAGRAM", "supported": False},
            {"name": "TikTok", "key": "TIKTOK", "supported": False}
        ]
    }