# app/services/oauth_service.py
import secrets
import httpx
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from .. import models
from ..config import settings

class OAuthService:
    """Handle OAuth flows for social media platforms"""
    
    # OAuth configurations
    OAUTH_CONFIGS = {
        "twitter": {
            "auth_url": "https://twitter.com/i/oauth2/authorize",
            "token_url": "https://api.twitter.com/2/oauth2/token",
            "client_id": settings.TWITTER_CLIENT_ID,
            "client_secret": settings.TWITTER_CLIENT_SECRET,
            "scope": "tweet.read tweet.write users.read offline.access",
            "redirect_uri": f"{settings.BACKEND_URL}/auth/oauth/twitter/callback"
        },
        "facebook": {
            "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
            "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
            "client_id": settings.FACEBOOK_APP_ID,
            "client_secret": settings.FACEBOOK_APP_SECRET,
            "scope": "pages_manage_posts,pages_read_engagement,pages_show_list,instagram_basic,instagram_content_publish",
            "redirect_uri": f"{settings.BACKEND_URL}/auth/oauth/facebook/callback"
        },
        "linkedin": {
            "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
            "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
            "scope": "openid profile email w_member_social",
            "redirect_uri": f"{settings.BACKEND_URL}/auth/oauth/linkedin/callback"
        },
        "instagram": {
            "auth_url": "https://api.instagram.com/oauth/authorize",
            "token_url": "https://api.instagram.com/oauth/access_token",
            "client_id": settings.FACEBOOK_APP_ID,
            "client_secret": settings.FACEBOOK_APP_SECRET,
            "scope": "user_profile,user_media",
            "redirect_uri": f"{settings.BACKEND_URL}/auth/oauth/instagram/callback"
        },
        "tiktok": {
            "auth_url": "https://www.tiktok.com/v2/auth/authorize/",
            "token_url": "https://open.tiktokapis.com/v2/oauth/token/",
            "client_id": settings.TIKTOK_CLIENT_ID,
            "client_secret": settings.TIKTOK_CLIENT_SECRET,
            "scope": "user.info.basic,video.list,video.upload",
            "redirect_uri": f"{settings.BACKEND_URL}/auth/oauth/tiktok/callback"
        },
        "youtube": {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
            "redirect_uri": f"{settings.BACKEND_URL}/auth/oauth/youtube/callback"
        }
    }

    @classmethod
    async def initiate_oauth(cls, user_id: int, platform: str) -> str:
        """
        Initiate OAuth flow for a platform
        Returns the authorization URL to redirect user to
        """
        platform = platform.lower()
        
        if platform not in cls.OAUTH_CONFIGS:
            raise ValueError(f"Unsupported platform: {platform}")
        
        config = cls.OAUTH_CONFIGS[platform]
        
        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Store state in cache/session (you should implement caching)
        # For now, we'll include user_id in state (encrypted in production!)
        state_with_user = f"{user_id}:{state}"
        
        # Build authorization URL
        params = {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "scope": config["scope"],
            "state": state_with_user,
            "response_type": "code"
        }
        
        # Platform-specific params
        if platform == "twitter":
            params["code_challenge"] = "challenge"  # Use PKCE in production
            params["code_challenge_method"] = "plain"
        elif platform == "youtube":
            params["access_type"] = "offline"
            params["prompt"] = "consent"
        elif platform == "tiktok":
            params["response_type"] = "code"
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        auth_url = f"{config['auth_url']}?{query_string}"
        
        return auth_url

    @classmethod
    async def handle_oauth_callback(
        cls, 
        platform: str, 
        code: str, 
        state: str,
        db: AsyncSession
    ) -> Dict:
        """
        Handle OAuth callback and exchange code for access token
        """
        platform = platform.lower()
        
        if platform not in cls.OAUTH_CONFIGS:
            return {"success": False, "error": "Unsupported platform"}
        
        config = cls.OAUTH_CONFIGS[platform]
        
        # Extract user_id from state (implement proper validation!)
        try:
            user_id = int(state.split(":")[0])
        except:
            return {"success": False, "error": "Invalid state parameter"}
        
        # Exchange authorization code for access token
        try:
            async with httpx.AsyncClient() as client:
                # Prepare token request based on platform
                token_params = {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": config["redirect_uri"],
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"]
                }
                
                # Platform-specific token request handling
                if platform == "instagram":
                    token_response = await client.post(
                        config["token_url"],
                        data=token_params
                    )
                elif platform == "tiktok":
                    token_response = await client.post(
                        config["token_url"],
                        json=token_params,
                        headers={"Content-Type": "application/json"}
                    )
                else:
                    token_response = await client.post(
                        config["token_url"],
                        data=token_params,
                        headers={"Content-Type": "application/x-www-form-urlencoded"}
                    )
                
                if token_response.status_code != 200:
                    print(f"Token exchange failed: {token_response.status_code} - {token_response.text}")
                    return {
                        "success": False, 
                        "error": f"Token exchange failed: {token_response.text}"
                    }
                
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in")
                
                if not access_token:
                    print("No access token received")
                    return {"success": False, "error": "No access token received"}
                
                print(f"Access token received for {platform}")
                
                # Get user profile from platform
                user_info = await cls._get_platform_user_info(
                    platform, 
                    access_token
                )
                
                if not user_info:
                    print(f"Failed to get user info from {platform}")
                    return {"success": False, "error": f"Failed to get user profile from {platform}"}
                
                print(f"User info retrieved: {user_info}")
                
                # Save connection to database
                connection = await cls._save_connection(
                    db=db,
                    user_id=user_id,
                    platform=platform,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in,
                    platform_user_id=user_info.get("user_id"),
                    platform_username=user_info.get("username"),
                    platform_name=user_info.get("name")
                )
                
                print(f"Connection saved: {connection.id}")
                
                return {
                    "success": True,
                    "connection_id": connection.id,
                    "platform": platform,
                    "username": user_info.get("username") or user_info.get("name")
                }
                
        except Exception as e:
            print(f"OAuth callback error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    @classmethod
    async def _get_platform_user_info(cls, platform: str, access_token: str) -> Optional[Dict]:
        """
        Get user info from platform API
        Returns: {"user_id": str, "username": str, "name": str}
        """
        try:
            async with httpx.AsyncClient() as client:
                if platform == "twitter":
                    response = await client.get(
                        "https://api.twitter.com/2/users/me",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        user_data = data.get("data", {})
                        return {
                            "user_id": user_data.get("id"),
                            "username": user_data.get("username"),
                            "name": user_data.get("name")
                        }
                
                elif platform == "facebook":
                    response = await client.get(
                        f"https://graph.facebook.com/me?fields=id,name&access_token={access_token}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            "user_id": data.get("id"),
                            "username": data.get("id"),  # Facebook doesn't have username
                            "name": data.get("name")
                        }
                
                elif platform == "linkedin":
                    # Get user ID first
                    response = await client.get(
                        "https://api.linkedin.com/v2/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            "user_id": data.get("sub"),  # LinkedIn uses 'sub' for user ID
                            "username": data.get("email", "").split("@")[0],  # Use email prefix as username
                            "name": data.get("name") or f"{data.get('given_name', '')} {data.get('family_name', '')}".strip()
                        }
                    else:
                        print(f"LinkedIn API error: {response.status_code} - {response.text}")
                
                elif platform == "instagram":
                    response = await client.get(
                        f"https://graph.instagram.com/me?fields=id,username&access_token={access_token}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            "user_id": data.get("id"),
                            "username": data.get("username"),
                            "name": data.get("username")
                        }
                
                elif platform == "tiktok":
                    response = await client.get(
                        "https://open.tiktokapis.com/v2/user/info/?fields=open_id,union_id,avatar_url,display_name",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        user_data = data.get("data", {}).get("user", {})
                        return {
                            "user_id": user_data.get("open_id"),
                            "username": user_data.get("display_name"),
                            "name": user_data.get("display_name")
                        }
                
                elif platform == "youtube":
                    response = await client.get(
                        "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("items", [])
                        if items:
                            channel = items[0]
                            return {
                                "user_id": channel.get("id"),
                                "username": channel.get("snippet", {}).get("title"),
                                "name": channel.get("snippet", {}).get("title")
                            }
                
        except Exception as e:
            print(f"Error getting platform user info: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        return None

    @classmethod
    async def _save_connection(
        cls,
        db: AsyncSession,
        user_id: int,
        platform: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_in: Optional[int],
        platform_user_id: Optional[str],
        platform_username: Optional[str],
        platform_name: Optional[str] = None
    ) -> models.SocialConnection:
        """Save or update social connection"""
        
        # Ensure we have required fields
        if not platform_user_id:
            platform_user_id = f"temp_{platform}_{user_id}"  # Fallback
        
        if not platform_username:
            platform_username = platform_user_id
        
        # Check if connection already exists
        result = await db.execute(
            select(models.SocialConnection).where(
                models.SocialConnection.user_id == user_id,
                models.SocialConnection.platform == platform.upper()
            )
        )
        connection = result.scalar_one_or_none()
        
        if connection:
            # Update existing connection
            connection.platform_user_id = platform_user_id
            connection.platform_username = platform_username
            connection.username = platform_name or platform_username  # For backward compatibility
            connection.access_token = access_token
            connection.refresh_token = refresh_token
            connection.token_expires_at = (
                datetime.utcnow() + timedelta(seconds=expires_in)
                if expires_in else None
            )
            connection.is_active = True
            connection.last_synced = datetime.utcnow()
            connection.updated_at = datetime.utcnow()
        else:
            # Create new connection
            connection = models.SocialConnection(
                user_id=user_id,
                platform=platform.upper(),
                platform_user_id=platform_user_id,
                platform_username=platform_username,
                username=platform_name or platform_username,  # For backward compatibility
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=(
                    datetime.utcnow() + timedelta(seconds=expires_in)
                    if expires_in else None
                ),
                is_active=True,
                last_synced=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(connection)
        
        await db.commit()
        await db.refresh(connection)
        
        return connection

    @classmethod
    async def refresh_access_token(
        cls,
        db: AsyncSession,
        connection_id: int
    ) -> bool:
        """Refresh an expired access token"""
        
        result = await db.execute(
            select(models.SocialConnection).where(
                models.SocialConnection.id == connection_id
            )
        )
        connection = result.scalar_one_or_none()
        
        if not connection or not connection.refresh_token:
            return False
        
        platform = connection.platform.lower()
        config = cls.OAUTH_CONFIGS.get(platform)
        
        if not config:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config["token_url"],
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": connection.refresh_token,
                        "client_id": config["client_id"],
                        "client_secret": config["client_secret"]
                    }
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    connection.access_token = token_data.get("access_token")
                    if token_data.get("refresh_token"):
                        connection.refresh_token = token_data.get("refresh_token")
                    
                    expires_in = token_data.get("expires_in")
                    if expires_in:
                        connection.token_expires_at = (
                            datetime.utcnow() + timedelta(seconds=expires_in)
                        )
                    
                    await db.commit()
                    return True
        except Exception as e:
            print(f"Error refreshing token: {e}")
            return False
        
        return False