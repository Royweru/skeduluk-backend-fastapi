# app/routers/auth.py
from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr,field_validator
from sqlalchemy import select
from .. import models, auth
from ..database import get_async_db
from ..services.auth_service import AuthService
from ..services.oauth_service import OAuthService
from ..config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])


class UserRegister(BaseModel):
    email: EmailStr
    username: str
    password: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        # Warn about extremely long passwords but don't reject them
        if len(v.encode('utf-8')) > 200:
            raise ValueError('Password is unreasonably long')
        return v

class VerifyEmail(BaseModel):
    token: str

class ForgotPassword(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    token: str
    password: str

@router.post("/register")
async def register(
    user_data: UserRegister ,
    db: AsyncSession = Depends(get_async_db)
):
    """Register a new user"""
    
    # Check if user exists
    result = await db.execute(
        select(models.User).where(models.User.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    result = await db.execute(
        select(models.User).where(models.User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create user
    user = await AuthService.create_user_with_verification(
        db, user_data.email, user_data.username, user_data.password
    )
    
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "is_email_verified": user.is_email_verified,
        "message": "Registration successful! Please check your email to verify your account."
    }

@router.post("/verify-email")
async def verify_email(
    data: VerifyEmail,
    db: AsyncSession = Depends(get_async_db)
):
    """Verify user email"""
    
    success = await AuthService.verify_email(db, data.token)
    
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    
    return {"message": "Email verified successfully!"}

@router.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_db)
):
    """Login and get access token"""
    
    user = await AuthService.authenticate_user(
        db, form_data.username, form_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(hours=24)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPassword,
    db: AsyncSession = Depends(get_async_db)
):
    """Initiate password reset"""
    
    success = await AuthService.initiate_password_reset(db, data.email)
    
    return {"message": "If an account with that email exists, a password reset link has been sent."}

@router.post("/reset-password")
async def reset_password(
    data: ResetPassword,
    db: AsyncSession = Depends(get_async_db)
):
    """Reset password with token"""
    
    success = await AuthService.reset_password(db, data.token, data.password)
    
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    return {"message": "Password reset successfully!"}


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
    
    # Redirect back to frontend with result
    if result["success"]:
        # Success - redirect to dashboard
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/overview?connected={platform}&success=true",
            status_code=302
        )
    else:
        # Error - redirect with error message
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/overview?error={result['error']}",
            status_code=302
        )