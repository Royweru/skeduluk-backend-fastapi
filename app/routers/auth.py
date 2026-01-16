# app/routers/auth.py
from datetime import timedelta
from urllib.parse import quote  
from typing import Annotated,Dict,List,Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select

from .. import models, auth
from ..utils.security import verify_password , get_password_hash
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
    user_data: UserRegister,
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


# app/routers/auth.py

@router.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_db)
):
    """Login and get access token - accepts username or email"""
    
    # Try to find user by username first
    result = await db.execute(
        select(models.User).where(models.User.username == form_data.username)
    )
    user = result.scalar_one_or_none()
    
    # If not found by username, try email
    if not user:
        result = await db.execute(
            select(models.User).where(models.User.email == form_data.username)
        )
        user = result.scalar_one_or_none()
    
    # Verify password
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    
    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in"
        )
    
    access_token_expires = timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
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

# Add to your test endpoint
@router.post("/test-email")
async def test_email(
    email: str = Body(default='weruroy347@gmail.com', embed=True)  
):
    """Test endpoint to verify email configuration"""
    from ..services.email_service import email_service
    
    print(f"📧 Testing email to: {email}")
    print(f"SMTP Server: {email_service.smtp_server}:{email_service.smtp_port}")
    print(f"SMTP Username configured: {bool(email_service.smtp_username)}")
    print(f"SMTP Password configured: {bool(email_service.smtp_password)}")
    
    result = await email_service.send_verification_email(email, "test-token-123")
    
    return {
        "success": result,
        "message": f"Email {'sent successfully' if result else 'failed to send'}",
        "email": email,
        "config": {
            "smtp_server": email_service.smtp_server,
            "smtp_port": email_service.smtp_port,
            "has_credentials": bool(email_service.smtp_username and email_service.smtp_password)
        }
    }


