import secrets
import hashlib
import base64
import redis
from typing import Dict, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from ..config import settings
from app import models

# --- Upstash Redis Connection with SSL ---
try:
    REDIS_URL = settings.CELERY_BROKER_URL
    
    # Upstash requires SSL - ensure URL uses rediss:// or add ssl params
    if REDIS_URL.startswith("redis://") and "upstash.io" in REDIS_URL:
        REDIS_URL = REDIS_URL.replace("redis://", "rediss://")
        print(f"⚠️  Converted Redis URL to use SSL (rediss://)")
    
    print(f"🔍 Connecting to Upstash Redis...")
    
    # Connect with SSL support
    redis_client = redis.from_url(
        REDIS_URL,
        db=1,  # Use db=1 to keep OAuth state separate from Celery
        decode_responses=True,
        ssl_cert_reqs=None,  # Disable SSL certificate verification for Upstash
        socket_connect_timeout=10,
        socket_timeout=10
    )
    
    # Test connection
    redis_client.ping()
    print("✅ Connected to Upstash Redis for OAuth state.")
    
except redis.exceptions.ConnectionError as e:
    print(f"❌ CRITICAL: Could not connect to Upstash Redis. {e}")
    print("💡 Make sure CELERY_BROKER_URL uses 'rediss://' (with SSL)")
    redis_client = None
except Exception as e:
    print(f"❌ Unexpected Redis error: {e}")
    redis_client = None

# --- OAuth Configuration ---
BASE_URL = settings.BACKEND_URL.rstrip("/")
CALLBACK_PATH = "/auth/oauth/callback"

OAUTH_CONFIGS = {
    "twitter": {
        "client_id": settings.TWITTER_CLIENT_ID,
        "client_secret": settings.TWITTER_CLIENT_SECRET,
        "auth_url": "https://twitter.com/i/oauth2/authorize",
        "token_url": "https://api.twitter.com/2/oauth2/token",
        "revoke_url": "https://api.twitter.com/2/oauth2/revoke",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/twitter",
        "scope": "tweet.read tweet.write users.read offline.access",
        "user_info_url": "https://api.twitter.com/2/users/me",
        "uses_pkce": True,
        "token_auth_method": "basic"
    },
    "facebook": {
        "client_id": settings.FACEBOOK_APP_ID,
        "client_secret": settings.FACEBOOK_APP_SECRET,
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/facebook",
        "scope": "public_profile,email,instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement",
        "user_info_url": "https://graph.facebook.com/me?fields=id,name,email",
        "uses_pkce": False,
        "token_auth_method": "body"
    },
    "linkedin": {
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/linkedin",
        "scope": "profile email openid w_member_social",
        "user_info_url": "https://api.linkedin.com/v2/userinfo",
        "uses_pkce": False,
        "token_auth_method": "body"
    },
    "google": {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/google",
        "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email openid",
        "user_info_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "uses_pkce": True,
        "token_auth_method": "body",
        "auth_params": {
            "access_type": "offline",
            "prompt": "consent"
        }
    }
}


class OAuthService:
    """OAuth Service with Upstash Redis for PKCE state management"""
    
    @staticmethod
    def _check_redis():
        if not redis_client:
            raise HTTPException(
                status_code=503,
                detail="OAuth service unavailable. Redis connection failed. Check CELERY_BROKER_URL and ensure it uses 'rediss://' for SSL."
            )

    @staticmethod
    def _generate_code_verifier() -> str:
        """Generate a cryptographically random code verifier"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

    @staticmethod
    def _generate_code_challenge(verifier: str) -> str:
        """Generate code challenge from verifier using S256 method"""
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

    @classmethod
    async def initiate_oauth(cls, user_id: int, platform: str) -> str:
        """
        Initiate OAuth flow with PKCE and Redis state.
        Returns the authorization URL to redirect user to.
        """
        cls._check_redis()
        platform = platform.lower()

        if platform not in OAUTH_CONFIGS:
            raise ValueError(f"Unsupported platform: {platform}")

        config = OAUTH_CONFIGS[platform]
        if not all([config.get("client_id"), config.get("redirect_uri")]):
            raise HTTPException(
                status_code=500,
                detail=f"OAuth for {platform} is not configured. Missing CLIENT_ID or REDIRECT_URI."
            )

        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(32)
        state_with_user = f"{user_id}:{state}"
        
        params = {
            "response_type": "code",
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "scope": config["scope"],
            "state": state_with_user,
        }
        
        # Add any extra auth params (e.g., for Google)
        params.update(config.get("auth_params", {}))

        if config.get("uses_pkce", False):
            code_verifier = cls._generate_code_verifier()
            code_challenge = cls._generate_code_challenge(code_verifier)
            
            params.update({
                "code_challenge": code_challenge,
                "code_challenge_method": "S256"
            })
            
            # Store verifier in Redis with 10-minute TTL
            try:
                redis_client.set(f"pkce:{state_with_user}", code_verifier, ex=600)
                print(f"✅ Stored PKCE verifier in Redis for state: {state_with_user[:20]}...")
            except Exception as e:
                print(f"❌ Failed to store PKCE verifier in Redis: {e}")
                raise HTTPException(
                    status_code=503,
                    detail="Failed to store OAuth state. Please try again."
                )

        query_string = urlencode(params)
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
        Handle OAuth callback and exchange code for access token.
        Uses Redis to retrieve PKCE verifier.
        """
        cls._check_redis()
        platform = platform.lower()

        if platform not in OAUTH_CONFIGS:
            return {"success": False, "error": "Unsupported platform"}

        config = OAUTH_CONFIGS[platform]

        # Extract user_id from state
        try:
            user_id = int(state.split(":")[0])
        except (ValueError, IndexError, TypeError):
            return {"success": False, "error": "Invalid state parameter"}

        try:
            token_params = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config["redirect_uri"],
                "client_id": config["client_id"],
            }
            
            if config.get("uses_pkce", False):
                # Retrieve the code_verifier from Redis
                try:
                    code_verifier = redis_client.get(f"pkce:{state}")
                    
                    if not code_verifier:
                        return {
                            "success": False,
                            "error": "PKCE verifier not found or expired. Please try again."
                        }
                    
                    # Clean up used verifier immediately
                    redis_client.delete(f"pkce:{state}")
                    print(f"✅ Retrieved and deleted PKCE verifier from Redis")
                    
                    token_params["code_verifier"] = code_verifier
                    
                except Exception as e:
                    print(f"❌ Redis error retrieving PKCE verifier: {e}")
                    return {
                        "success": False,
                        "error": "Failed to retrieve OAuth state. Please try again."
                    }

            # Handle different token auth methods
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            auth = None

            if config.get("token_auth_method") == "basic":
                auth = (config["client_id"], config["client_secret"])
            else:
                token_params["client_secret"] = config["client_secret"]

            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    config["token_url"],
                    data=token_params,
                    headers=headers,
                    auth=auth,
                    timeout=30.0
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
                    return {"success": False, "error": "No access token received"}
                
                # Get user profile from platform
                user_info = await cls._get_platform_user_info(
                    platform, access_token, config["user_info_url"]
                )
                
                if not user_info:
                    return {"success": False, "error": f"Failed to get user profile from {platform}"}
                
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
                    platform_name=user_info.get("name"),
                    platform_email=user_info.get("email")
                )
                
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
    async def refresh_access_token(
        cls,
        connection: models.SocialConnection,
        db: AsyncSession
    ) -> Optional[Dict]:
        """Refresh an expired access token"""
        platform = connection.platform.lower()
        refresh_token = connection.refresh_token

        if not refresh_token:
            print(f"No refresh token for connection {connection.id}")
            return None
        
        if platform not in OAUTH_CONFIGS:
            return None
        
        config = OAUTH_CONFIGS[platform]
        
        try:
            refresh_params = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": config["client_id"],
            }

            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            auth = None

            if config.get("token_auth_method") == "basic":
                auth = (config["client_id"], config["client_secret"])
            else:
                refresh_params["client_secret"] = config["client_secret"]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config["token_url"],
                    data=refresh_params,
                    headers=headers,
                    auth=auth,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    print(f"Token refresh failed for conn {connection.id}: {response.status_code} - {response.text}")
                    connection.is_active = False
                    await db.commit()
                    return None
                
                token_data = response.json()
                new_access_token = token_data.get("access_token")
                new_refresh_token = token_data.get("refresh_token", refresh_token)
                expires_in = token_data.get("expires_in")
                
                # Update connection
                connection.access_token = new_access_token
                connection.refresh_token = new_refresh_token
                connection.token_expires_at = (
                    datetime.utcnow() + timedelta(seconds=int(expires_in))
                    if expires_in else None
                )
                connection.updated_at = datetime.utcnow()
                connection.is_active = True
                await db.commit()
                
                return {
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token,
                    "expires_in": expires_in
                }
                
        except Exception as e:
            print(f"Token refresh error for conn {connection.id}: {str(e)}")
            return None

    @classmethod
    async def _get_platform_user_info(
        cls, platform: str, access_token: str, user_info_url: str
    ) -> Optional[Dict]:
        """Get user info from platform API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    user_info_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    print(f"{platform} API error: {response.status_code} - {response.text}")
                    return None

                data = response.json()
                
                if platform == "twitter":
                    user_data = data.get("data", {})
                    return {
                        "user_id": user_data.get("id"),
                        "username": user_data.get("username"),
                        "name": user_data.get("name"),
                        "email": None
                    }
                elif platform == "facebook":
                    return {
                        "user_id": data.get("id"),
                        "username": data.get("name"),
                        "name": data.get("name"),
                        "email": data.get("email")
                    }
                elif platform == "linkedin":
                    return {
                        "user_id": data.get("sub"),
                        "username": f"{data.get('given_name', '')} {data.get('family_name', '')}".strip(),
                        "name": f"{data.get('given_name', '')} {data.get('family_name', '')}".strip(),
                        "email": data.get("email")
                    }
                elif platform == "google":
                    return {
                        "user_id": data.get("sub"),
                        "username": data.get("email"),
                        "name": data.get("name"),
                        "email": data.get("email")
                    }
                
        except Exception as e:
            print(f"Error getting {platform} user info: {e}")
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
        platform_username: Optional[str] = None,
        platform_name: Optional[str] = None,
        platform_email: Optional[str] = None
    ) -> models.SocialConnection:
        """Save or update social connection"""
        
        if not platform_user_id:
            raise ValueError("platform_user_id is required to save connection")
        
        if not platform_username:
            platform_username = platform_name or platform_user_id
        
        # Check if connection exists
        result = await db.execute(
            select(models.SocialConnection).where(
                models.SocialConnection.user_id == user_id,
                models.SocialConnection.platform == platform.upper(),
                models.SocialConnection.platform_user_id == platform_user_id
            )
        )
        connection = result.scalar_one_or_none()
        
        expires_at = (
            datetime.utcnow() + timedelta(seconds=int(expires_in))
            if expires_in else None
        )
        
        if connection:
            connection.platform_username = platform_username
            connection.username = platform_name or platform_username
            connection.access_token = access_token
            connection.refresh_token = refresh_token
            connection.token_expires_at = expires_at
            connection.is_active = True
            connection.last_synced = datetime.utcnow()
            connection.updated_at = datetime.utcnow()
        else:
            connection = models.SocialConnection(
                user_id=user_id,
                platform=platform.upper(),
                platform_user_id=platform_user_id,
                platform_username=platform_username,
                username=platform_name or platform_username,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=expires_at,
                is_active=True,
                last_synced=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(connection)
        
        await db.commit()
        await db.refresh(connection)
        
        return connection