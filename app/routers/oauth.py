# app/routers/auth.py
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, models, schemas, auth
from ..database import get_async_db
from ..services.oauth_service import OAuthService
from ..config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])



@router.get("/oauth/{platform}/authorize")
async def oauth_authorize(
    platform: str,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """Initiate OAuth flow for a social platform"""
    try:
        auth_url = await OAuthService.initiate_oauth(current_user.id, platform)
        return {"auth_url": auth_url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/oauth/{platform}/callback")
async def oauth_callback(
    platform: str,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Handle OAuth callback from social platform"""
    result = await OAuthService.handle_oauth_callback(platform, code, state, db)
    
    if result["success"]:
        return {"message": f"Successfully connected to {platform}"}
    else:
        raise HTTPException(status_code=400, detail=result["error"])