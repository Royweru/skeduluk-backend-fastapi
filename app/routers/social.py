# app/routers/social.py
import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from urllib.parse import quote  
from typing import List,  Optional
import httpx

from ..config import settings
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

# Routes for facebook pages connection
@router.get("/facebook/pages")
async def get_facebook_pages(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get list of Facebook Pages user can manage"""
    # Get user's Facebook connection
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.user_id == current_user.id,
            models.SocialConnection.platform == "FACEBOOK",
            models.SocialConnection.is_active == True
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(404, "Facebook not connected")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch pages from Facebook
            response = await client.get(
                "https://graph.facebook.com/v20.0/me/accounts",
                params={
                    "access_token": connection.access_token,
                    "fields": "id,name,category,access_token,picture"
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(500, f"Failed to fetch pages: {response.text}")
            
            pages_data = response.json()
            pages = pages_data.get("data", [])
            
            if not pages:
                return {
                    "pages": [],
                    "message": "No Facebook Pages found. You need to create a Facebook Page first.",
                    "create_page_url": "https://www.facebook.com/pages/create"
                }
            
            # Format pages for frontend
            formatted_pages = []
            for page in pages:
                formatted_pages.append({
                    "id": page["id"],
                    "name": page["name"],
                    "category": page.get("category", "Unknown"),
                    "access_token": page["access_token"],
                    "picture_url": page.get("picture", {}).get("data", {}).get("url"),
                    "is_selected": page["id"] == connection.facebook_page_id
                })
            
            return {
                "pages": formatted_pages,
                "selected_page_id": connection.facebook_page_id,
                "total": len(formatted_pages)
            }
            
    except Exception as e:
        print(f"Error fetching Facebook pages: {e}")
        raise HTTPException(500, f"Error fetching pages: {str(e)}")


@router.post("/facebook/pages/select")
async def select_facebook_page(
    page_id: str,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Select which Facebook Page to use for posting"""
    # Get connection
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.user_id == current_user.id,
            models.SocialConnection.platform == "FACEBOOK",
            models.SocialConnection.is_active == True
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(404, "Facebook not connected")
    
    try:
        # Fetch pages to validate selection and get page token
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://graph.facebook.com/v20.0/me/accounts",
                params={
                    "access_token": connection.access_token,
                    "fields": "id,name,category,access_token,picture"
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(500, "Failed to fetch pages")
            
            pages = response.json().get("data", [])
            selected_page = next((p for p in pages if p["id"] == page_id), None)
            
            if not selected_page:
                raise HTTPException(404, "Page not found or not accessible")
            
            # Update connection with selected page info
            connection.facebook_page_id = selected_page["id"]
            connection.facebook_page_name = selected_page["name"]
            connection.facebook_page_access_token = selected_page["access_token"]
            connection.facebook_page_category = selected_page.get("category")
            connection.facebook_page_picture = selected_page.get("picture", {}).get("data", {}).get("url")
            connection.updated_at = datetime.datetime.utcnow()
            
            await db.commit()
            await db.refresh(connection)
            
            return {
                "success": True,
                "message": f"Successfully selected page: {selected_page['name']}",
                "page": {
                    "id": selected_page["id"],
                    "name": selected_page["name"],
                    "category": selected_page.get("category"),
                    "picture_url": selected_page.get("picture", {}).get("data", {}).get("url")
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error selecting Facebook page: {e}")
        raise HTTPException(500, f"Failed to select page: {str(e)}")


@router.get("/facebook/selected-page")
async def get_selected_facebook_page(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get currently selected Facebook Page"""
    result = await db.execute(
        select(models.SocialConnection).where(
            models.SocialConnection.user_id == current_user.id,
            models.SocialConnection.platform == "FACEBOOK",
            models.SocialConnection.is_active == True
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(404, "Facebook not connected")
    
    if not connection.facebook_page_id:
        return {
            "has_selection": False,
            "message": "No Facebook Page selected"
        }
    
    return {
        "has_selection": True,
        "page": {
            "id": connection.facebook_page_id,
            "name": connection.facebook_page_name,
            "category": connection.facebook_page_category,
            "picture_url": connection.facebook_page_picture
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
        print(f" OAuth initiate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oauth/callback/{platform}")
async def oauth_callback(
    platform: str,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    error_description: Optional[str] = Query(None),
    
    # OAuth 1.0a parameters (Twitter)
    oauth_token: Optional[str] = Query(None),
    oauth_verifier: Optional[str] = Query(None),
    denied: Optional[str] = Query(None),
):
    print(f"\n{'='*60}")
    print(f" OAuth Callback Received")
    print(f"Platform: {platform}")
    print(f"Code: {code[:20] if code else 'None'}...")
    print(f"OAuth Token: {oauth_token[:20] if oauth_token else 'None'}...")
    print(f"OAuth Verifier: {oauth_verifier[:20] if oauth_verifier else 'None'}...")
    print(f"State: {state[:30] if state else 'None'}...")
    print(f"Error: {error or 'None'}")
    print(f"{'='*60}\n")
    """
    Handle OAuth callback from social platform
    Returns HTML that closes popup and communicates with parent window
    """
    # Check for user denial
     # Check for user denial
    if denied:
        print(f" User denied authorization")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/overview?error={quote('You cancelled the connection')}"
        )
    
    if error:
        error_msg = error_description or error
        print(f" OAuth error: {error_msg}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/overview?error={quote(error_msg)}"
        )
    
    #  Validate that we have EITHER OAuth 1.0a OR OAuth 2.0 parameters
    is_oauth1 = bool(oauth_token and oauth_verifier)
    is_oauth2 = bool(code and state)  # OAuth 2.0 requires state
    
    if not is_oauth1 and not is_oauth2:
        print(f" Missing required parameters")
        print(f"   OAuth 1.0a needs: oauth_token + oauth_verifier")
        print(f"   OAuth 2.0 needs: code + state")
        print(f"   Got: code={bool(code)}, state={bool(state)}, oauth_token={bool(oauth_token)}, oauth_verifier={bool(oauth_verifier)}")
        
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/overview?error={quote('Missing authorization parameters')}"
        )
    
    if not is_oauth1 and not is_oauth2:
        print(f" Missing required parameters")
        print(f"   OAuth 1.0a needs: oauth_token + oauth_verifier")
        print(f"   OAuth 2.0 needs: code + state")
        print(f"   Got: code={bool(code)}, state={bool(state)}, oauth_token={bool(oauth_token)}, oauth_verifier={bool(oauth_verifier)}")
        
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/overview?error={quote('Missing authorization parameters')}"
        )
    
    
    result = await OAuthService.handle_oauth_callback(
            platform=platform,
            code=code,
            state=state,
            oauth_token=oauth_token,
            oauth_verifier=oauth_verifier,
            db=db,
            error=error
        )
    
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
                <div class="icon"></div>
                <h1>Connected Successfully!</h1>
                <p>Your {platform_display} account has been linked</p>
                {f'<p class="username">{username}</p>' if username else ''}
                <div class="loader"></div>
                <p style="margin-top: 1rem; font-size: 0.875rem;">Closing window...</p>
            </div>
            <script>
                console.log(' OAuth callback successful for {platform}');
                
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
                        console.error(' Error sending message:', error);
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
                <div class="icon"></div>
                <h1>Connection Failed</h1>
                <p style="margin-bottom: 1rem;">Failed to connect {platform_display}</p>
                <div class="error-message">{error_message}</div>
                <p>This window will close in 3 seconds...</p>
            </div>
            <script>
                console.error(' OAuth callback failed for {platform}:', '{error_message}');
                
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
                        console.error(' Error sending message:', error);
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
