# app/routers/auth.py
from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, field_validator
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
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
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

@router.post("/test-email")
async def test_email(
    email: str = Body(default='weruroy347@gmail.com', embed=True)  
):
    """Test endpoint to verify email configuration"""
    from ..services.email_service import email_service
    
    print(f"📧 Sending test email to: {email}")
    
    result = await email_service.send_verification_email(
        email,
        "test-token-123"
    )
    
    return {
        "success": result,
        "message": f"Email {'sent successfully' if result else 'failed to send'}",
        "email": email
    }

# ============== OAuth Routes ==============

@router.get("/oauth/{platform}/authorize")
async def oauth_authorize(
    platform: str,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Initiate OAuth flow for a social platform
    Returns the authorization URL for the frontend to open in a popup
    """
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
    """
    Handle OAuth callback from social platform
    Returns HTML that closes popup and communicates with parent window
    """
    result = await OAuthService.handle_oauth_callback(platform, code, state, db)
    
    # Return HTML that closes popup and communicates with parent window
    if result["success"]:
        username = result.get("username", "")
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Connection Successful</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                }}
                .container {{
                    text-align: center;
                    padding: 2rem;
                    max-width: 400px;
                }}
                .icon {{
                    font-size: 4rem;
                    margin-bottom: 1rem;
                    animation: scaleIn 0.5s ease-out;
                }}
                @keyframes scaleIn {{
                    from {{
                        transform: scale(0);
                        opacity: 0;
                    }}
                    to {{
                        transform: scale(1);
                        opacity: 1;
                    }}
                }}
                h1 {{
                    margin: 0 0 0.5rem 0;
                    font-size: 1.75rem;
                    font-weight: 600;
                }}
                p {{
                    margin: 0;
                    opacity: 0.9;
                    font-size: 1rem;
                }}
                .username {{
                    margin-top: 0.5rem;
                    font-weight: 600;
                    font-size: 1.1rem;
                }}
                .loader {{
                    margin: 1rem auto 0;
                    width: 40px;
                    height: 40px;
                    border: 3px solid rgba(255,255,255,0.3);
                    border-top-color: white;
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                }}
                @keyframes spin {{
                    to {{ transform: rotate(360deg); }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">✅</div>
                <h1>Connected Successfully!</h1>
                <p>Your {platform.title()} account has been linked</p>
                {f'<p class="username">{username}</p>' if username else ''}
                <div class="loader"></div>
                <p style="margin-top: 1rem; font-size: 0.875rem;">Closing window...</p>
            </div>
            <script>
                console.log('OAuth callback successful for {platform}');
                
                // Send message to parent window
                if (window.opener) {{
                    try {{
                        window.opener.postMessage({{
                            type: 'OAUTH_SUCCESS',
                            platform: '{platform}',
                            username: '{username}'
                        }}, '{settings.FRONTEND_URL}');
                        console.log('Message sent to parent window');
                    }} catch (error) {{
                        console.error('Error sending message:', error);
                    }}
                }}
                
                // Close window after 1.5 seconds
                setTimeout(() => {{
                    console.log('Closing window...');
                    window.close();
                    
                    // Fallback: try to close again after 500ms
                    setTimeout(() => {{
                        if (!window.closed) {{
                            window.close();
                        }}
                    }}, 500);
                }}, 1500);
            </script>
        </body>
        </html>
        """, status_code=200)
    else:
        error_message = result.get("error", "Unknown error occurred")
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Connection Failed</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    color: white;
                    padding: 20px;
                }}
                .container {{
                    text-align: center;
                    padding: 2rem;
                    max-width: 500px;
                }}
                .icon {{
                    font-size: 4rem;
                    margin-bottom: 1rem;
                    animation: shake 0.5s ease-out;
                }}
                @keyframes shake {{
                    0%, 100% {{ transform: translateX(0); }}
                    25% {{ transform: translateX(-10px); }}
                    75% {{ transform: translateX(10px); }}
                }}
                h1 {{
                    margin: 0 0 1rem 0;
                    font-size: 1.75rem;
                    font-weight: 600;
                }}
                .error-message {{
                    margin: 1rem 0;
                    padding: 1rem;
                    background: rgba(255,255,255,0.2);
                    border-radius: 8px;
                    font-size: 0.875rem;
                    line-height: 1.5;
                    word-break: break-word;
                }}
                p {{
                    margin: 0;
                    opacity: 0.9;
                    font-size: 0.875rem;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">❌</div>
                <h1>Connection Failed</h1>
                <div class="error-message">{error_message}</div>
                <p>This window will close in 3 seconds...</p>
            </div>
            <script>
                console.error('OAuth callback failed for {platform}:', '{error_message}');
                
                // Send error to parent window
                if (window.opener) {{
                    try {{
                        window.opener.postMessage({{
                            type: 'OAUTH_ERROR',
                            platform: '{platform}',
                            error: '{error_message}'
                        }}, '{settings.FRONTEND_URL}');
                        console.log('Error message sent to parent window');
                    }} catch (error) {{
                        console.error('Error sending message:', error);
                    }}
                }}
                
                // Close window after 3 seconds
                setTimeout(() => {{
                    console.log('Closing window...');
                    window.close();
                    
                    // Fallback
                    setTimeout(() => {{
                        if (!window.closed) {{
                            window.close();
                        }}
                    }}, 500);
                }}, 3000);
            </script>
        </body>
        </html>
        """, status_code=200)