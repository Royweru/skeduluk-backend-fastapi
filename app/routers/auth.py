# app/routers/auth.py
from datetime import timedelta
from typing import Annotated,Dict,List
from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
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

# ============== OAuth Routes ==============

@router.get("/oauth/{platform}/authorize")
async def oauth_authorize(
    platform: str,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Initiate OAuth flow for a social platform
    Returns the authorization URL for the frontend to open in a popup
    
    Supports: twitter, facebook, instagram, youtube
    """
    try:
        auth_url = await OAuthService.initiate_oauth(current_user.id, platform)
        return {"auth_url": auth_url}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ OAuth initiate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oauth/callback/{platform}")
async def oauth_callback(
    platform: str,
    code: str = Query(...),
    state: str = Query(...),
    error: str = Query(default=None),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Handle OAuth callback from social platform
    Returns HTML that closes popup and communicates with parent window
    """
    result = await OAuthService.handle_oauth_callback(platform, code, state, db, error)
    
    # Return HTML that closes popup and communicates with parent window
    if result["success"]:
        username = result.get("username", "")
        platform_display = platform.title()
        
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
                <p>Your {platform_display} account has been linked</p>
                {f'<p class="username">{username}</p>' if username else ''}
                <div class="loader"></div>
                <p style="margin-top: 1rem; font-size: 0.875rem;">Closing window...</p>
            </div>
            <script>
                console.log('✅ OAuth callback successful for {platform}');
                
                // Send message to parent window
                if (window.opener) {{
                    try {{
                        window.opener.postMessage({{
                            type: 'OAUTH_SUCCESS',
                            platform: '{platform}',
                            username: '{username}'
                        }}, '*');
                        console.log('📤 Message sent to parent window');
                    }} catch (error) {{
                        console.error('❌ Error sending message:', error);
                    }}
                }}
                
                // Close window after 1.5 seconds
                setTimeout(() => {{
                    console.log('🚪 Closing window...');
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
        platform_display = platform.title()
        
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
                <p style="margin-bottom: 1rem;">Failed to connect {platform_display}</p>
                <div class="error-message">{error_message}</div>
                <p>This window will close in 3 seconds...</p>
            </div>
            <script>
                console.error('❌ OAuth callback failed for {platform}:', '{error_message}');
                
                // Send error to parent window
                if (window.opener) {{
                    try {{
                        window.opener.postMessage({{
                            type: 'OAUTH_ERROR',
                            platform: '{platform}',
                            error: '{error_message}'
                        }}, '*');
                        console.log('📤 Error message sent to parent window');
                    }} catch (error) {{
                        console.error('❌ Error sending message:', error);
                    }}
                }}
                
                // Close window after 3 seconds
                setTimeout(() => {{
                    console.log('🚪 Closing window...');
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


@router.get("/connections")
async def get_connections(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get all social media connections for the current user"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.user_id == current_user.id
        )
    )
    connections = result.scalars().all()
    
    return {
        "connections": [
            {
                "id": conn.id,
                "platform": conn.platform,
                "username": conn.username,
                "platform_username": conn.platform_username,
                "is_active": conn.is_active,
                "connected_at": conn.created_at.isoformat() if conn.created_at else None,
                "expires_at": conn.token_expires_at.isoformat() if conn.token_expires_at else None
            }
            for conn in connections
        ]
    }


@router.delete("/connections/{connection_id}")
async def delete_connection(
    connection_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Delete a social media connection"""
    from sqlalchemy import select, delete
    
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.id == connection_id,
            models.SocialConnection.user_id == current_user.id
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    await db.execute(
        delete(models.SocialConnection).where(
            models.SocialConnection.id == connection_id
        )
    )
    await db.commit()
    
    return {"message": f"{connection.platform} connection deleted successfully"}


@router.post("/connections/{connection_id}/refresh")
async def refresh_connection(
    connection_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Manually refresh a connection's access token"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.id == connection_id,
            models.SocialConnection.user_id == current_user.id
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    refresh_result = await OAuthService.refresh_access_token(connection, db)
    
    if not refresh_result:
        raise HTTPException(
            status_code=400,
            detail="Failed to refresh token. Please reconnect your account."
        )
    
    return {
        "message": "Token refreshed successfully",
        "expires_at": connection.token_expires_at.isoformat() if connection.token_expires_at else None
    }


@router.get("/platforms")
async def get_supported_platforms():
    """Get list of supported platforms and their configuration status"""
    from app.services.oauth_service import OAUTH_CONFIGS
    
    platforms = []
    for platform, config in OAUTH_CONFIGS.items():
        platforms.append({
            "id": platform,
            "name": config.get("platform_display_name", platform.title()),
            "configured": bool(config.get("client_id") and config.get("client_secret")),
            "uses_pkce": config.get("uses_pkce", False)
        })
    
    return {"platforms": platforms}

# ============== DEBUG ENDPOINTS ==============


@router.get("/oauth/debug/{platform}")
async def debug_oauth_config(platform: str):
    """
    Debug OAuth configuration for a specific platform.
    Shows configuration without sensitive data.
    """
    from app.services.oauth_service import OAUTH_CONFIGS, OAuthService
    
    platform = platform.lower()
    
    if platform not in OAUTH_CONFIGS:
        return {
            "error": f"Platform '{platform}' not supported",
            "supported_platforms": list(OAUTH_CONFIGS.keys())
        }
    
    config = OAUTH_CONFIGS[platform]
    
    # Validate configuration
    is_valid, error_msg = OAuthService.validate_config(platform)
    
    return {
        "platform": platform,
        "status": "✅ VALID" if is_valid else f"❌ INVALID: {error_msg}",
        "configuration": {
            "client_id": f"{config.get('client_id', 'NOT SET')[:15]}..." if config.get('client_id') else "NOT SET",
            "client_id_length": len(config.get('client_id', '')) if config.get('client_id') else 0,
            "client_secret_set": "YES ✅" if config.get('client_secret') else "NO ❌",
            "client_secret_length": len(config.get('client_secret', '')) if config.get('client_secret') else 0,
            "redirect_uri": config.get('redirect_uri', 'NOT SET'),
            "auth_url": config.get('auth_url'),
            "token_url": config.get('token_url'),
            "scopes": config.get('scope', 'NONE'),
            "uses_pkce": config.get('uses_pkce', False),
            "token_auth_method": config.get('token_auth_method', 'body'),
            "response_type": config.get('response_type', 'code'),
        },
        "warnings": _get_config_warnings(platform, config)
    }


def _get_config_warnings(platform: str, config: Dict) -> List[str]:
    """Get configuration warnings for a platform"""
    warnings = []
    
    # Check client ID length
    if config.get('client_id'):
        client_id_len = len(config['client_id'])
        if platform == 'twitter' and client_id_len < 20:
            warnings.append(f"⚠️ Twitter Client IDs are usually 20-30 chars, yours is {client_id_len}. Are you using the OAuth 2.0 Client ID (not API Key)?")
        if platform == 'facebook' and client_id_len < 10:
            warnings.append(f"⚠️ Facebook App IDs are usually 15+ digits, yours is {client_id_len}. Check your Facebook App ID.")
    
    # Check redirect URI
    if config.get('redirect_uri'):
        if 'localhost' in config['redirect_uri']:
            warnings.append("ℹ️ Using localhost redirect URI - make sure this is also in production config")
    
    # Platform-specific warnings
    if platform == 'twitter' and not config.get('uses_pkce'):
        warnings.append("❌ Twitter REQUIRES PKCE! Set uses_pkce to True")
    
    if platform == 'facebook' and 'pages_show_list' not in config.get('scope', ''):
        warnings.append("⚠️ Facebook scope missing 'pages_show_list' - you won't be able to post to pages")
    
    return warnings


@router.get("/oauth/test/{platform}")
async def test_oauth_flow(
    platform: str,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Generate OAuth URL for testing.
    Copy the URL and paste it in your browser to test the flow.
    """
    from app.services.oauth_service import OAuthService
    
    try:
        auth_url = await OAuthService.initiate_oauth(current_user.id, platform)
        
        return {
            "success": True,
            "platform": platform,
            "auth_url": auth_url,
            "instructions": [
                "1. Copy the 'auth_url' below",
                "2. Paste it in your browser",
                "3. Authorize the app",
                "4. Check your terminal logs for debugging info",
                "5. After redirect, check if connection was saved"
            ],
            "note": "Check your terminal/console for detailed debug logs"
        }
    except HTTPException as e:
        return {
            "success": False,
            "error": e.detail,
            "status_code": e.status_code
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/oauth/validate-setup")
async def validate_oauth_setup():
    """
    Validate OAuth setup for all platforms.
    Shows which platforms are properly configured.
    """
    from app.services.oauth_service import OAUTH_CONFIGS, OAuthService
    
    results = {}
    summary = {
        "total_platforms": len(OAUTH_CONFIGS),
        "configured": 0,
        "missing_config": 0,
        "errors": []
    }
    
    for platform in OAUTH_CONFIGS.keys():
        is_valid, error_msg = OAuthService.validate_config(platform)
        
        results[platform] = {
            "status": "✅ Ready" if is_valid else "❌ Not Ready",
            "error": error_msg if not is_valid else None,
            "redirect_uri": OAUTH_CONFIGS[platform].get('redirect_uri')
        }
        
        if is_valid:
            summary["configured"] += 1
        else:
            summary["missing_config"] += 1
            summary["errors"].append(f"{platform}: {error_msg}")
    
    return {
        "summary": summary,
        "platforms": results,
        "backend_url": settings.BACKEND_URL,
        "callback_path": "/auth/oauth/callback"
    }


