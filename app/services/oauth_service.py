# app/services/oauth_service.py
import secrets
import hashlib
import base64
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from jose import jwt, JWTError
import asyncio

from ..config import settings
from app import models

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
        # ✅ UPDATED: Minimal realistic scopes for social scheduler
        "scope": "tweet.read tweet.write users.read offline.access",
        "user_info_url": "https://api.twitter.com/2/users/me?user.fields=id,name,username,profile_image_url",
        "uses_pkce": True,
        "token_auth_method": "basic",
        "response_type": "code"
    },
    "facebook": {
        "client_id": settings.FACEBOOK_APP_ID,
        "client_secret": settings.FACEBOOK_APP_SECRET,
        "auth_url": "https://www.facebook.com/v20.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v20.0/oauth/access_token",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/facebook",
        # ✅ UPDATED: Start with basic permissions - add advanced later after App Review
        "scope": "public_profile,email",  # Minimal for Development Mode
        # For production (after App Review), add: pages_read_engagement,pages_manage_posts
        "user_info_url": "https://graph.facebook.com/v20.0/me?fields=id,name,email,picture",
        "uses_pkce": False,
        "token_auth_method": "body",
        "response_type": "code",
        "exchange_token": True  # Facebook needs long-lived token
    },
    "instagram": {
        "client_id": settings.FACEBOOK_APP_ID,
        "client_secret": settings.FACEBOOK_APP_SECRET,
        "auth_url": "https://www.facebook.com/v20.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v20.0/oauth/access_token",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/instagram",
        # ✅ UPDATED: Correct Instagram scopes (requires Business/Creator account)
        "scope": "instagram_basic,pages_show_list,business_management",  
        # For posting: add instagram_content_publish after App Review
        "user_info_url": "https://graph.facebook.com/v20.0/me?fields=id,name,picture",
        "uses_pkce": False,
        "token_auth_method": "body",
        "response_type": "code",
        "exchange_token": True,
        "platform_display_name": "Instagram"
    },
    "youtube": {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/youtube",
        # ✅ UPDATED: Correct YouTube scopes
        "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email",
        "user_info_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "uses_pkce": False,
        "token_auth_method": "body",
        "response_type": "code",
        "auth_params": {
            "access_type": "offline",
            "prompt": "consent"
        },
        "platform_display_name": "YouTube"
    }
}

class OAuthService:
    """OAuth Service with improved PKCE and state management"""

    @staticmethod
    def _generate_code_verifier() -> str:
        """Generate code verifier for PKCE (43-128 characters)"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

    @staticmethod
    def _generate_code_challenge(verifier: str) -> str:
        """Generate code challenge from verifier using S256"""
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

    @staticmethod
    def _generate_state() -> str:
        """Generate secure random state (at least 6 characters)"""
        return secrets.token_urlsafe(16)

    @classmethod
    async def initiate_oauth(cls, user_id: int, platform: str) -> str:
        """Initiate OAuth flow with proper PKCE and state management"""
        platform = platform.lower()
        if platform not in OAUTH_CONFIGS:
            raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

        config = OAUTH_CONFIGS[platform]
        if not all([config.get("client_id"), config.get("client_secret"), config.get("redirect_uri")]):
            raise HTTPException(status_code=500, detail=f"OAuth for {platform} is not configured.")

        # Generate state
        state = cls._generate_state()
        
        # State payload for JWT (expires in 15 minutes)
        state_payload = {
            "user_id": user_id,
            "platform": platform,
            "state": state,
            "exp": datetime.utcnow() + timedelta(minutes=15)
        }
        
        # Build authorization parameters
        params = {
            "response_type": config.get("response_type", "code"),
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "state": state
        }
        
        if config.get("scope"):
            params["scope"] = config["scope"]
        
        # Add any extra auth params
        params.update(config.get("auth_params", {}))

        # Handle PKCE
        if config.get("uses_pkce", False):
            code_verifier = cls._generate_code_verifier()
            code_challenge = cls._generate_code_challenge(code_verifier)
            params.update({
                "code_challenge": code_challenge,
                "code_challenge_method": "S256"
            })
            state_payload["pkce_verifier"] = code_verifier
        
        # Encode the state payload into a JWT
        state_jwt = jwt.encode(state_payload, settings.SECRET_KEY, algorithm="HS256")
        params["state"] = state_jwt

        # Build authorization URL
        query_string = urlencode(params, quote_via=quote)
        auth_url = f"{config['auth_url']}?{query_string}"
        
        print(f"🔗 OAuth URL for {platform}: {auth_url[:150]}...")
        return auth_url

    @classmethod
    async def handle_oauth_callback(
        cls, platform: str, code: str, state: str, db: AsyncSession, error: Optional[str] = None
    ) -> Dict:
        """Handle OAuth callback with proper error handling"""
        if error:
            return {"success": False, "error": f"Authorization denied: {error}"}

        platform = platform.lower()
        if platform not in OAUTH_CONFIGS:
            return {"success": False, "error": f"Unsupported platform: {platform}"}

        config = OAUTH_CONFIGS[platform]

        # Decode and validate state JWT
        try:
            state_payload = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
            
            if state_payload.get("platform") != platform:
                raise JWTError("Platform mismatch in state token")
            
            user_id = state_payload["user_id"]
            code_verifier = state_payload.get("pkce_verifier")

        except JWTError as e:
            print(f"❌ Invalid state token: {e}")
            return {"success": False, "error": "Invalid or expired connection link. Please try again."}

        try:
            # Exchange code for tokens
            token_params = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config["redirect_uri"],
                "client_id": config["client_id"],
            }
            
            if config.get("uses_pkce", False):
                if not code_verifier:
                    return {"success": False, "error": "PKCE verifier missing from state."}
                token_params["code_verifier"] = code_verifier
            
            if config.get("token_auth_method") != "basic":
                token_params["client_secret"] = config["client_secret"]

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
            
            auth = None
            if config.get("token_auth_method") == "basic":
                auth = (config["client_id"], config["client_secret"])

            async with httpx.AsyncClient(timeout=30.0) as client:
                token_response = await client.post(
                    config["token_url"],
                    data=token_params,
                    headers=headers,
                    auth=auth
                )

                if token_response.status_code != 200:
                    print(f"❌ Token exchange failed: {token_response.status_code} {token_response.text}")
                    return {"success": False, "error": f"Token exchange failed: {token_response.status_code}"}
                
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                
                if not access_token:
                    return {"success": False, "error": "No access token received"}

                # Exchange for long-lived token (Facebook/Instagram)
                if config.get("exchange_token"):
                    access_token, token_data = await cls._exchange_long_lived_token(
                        platform, access_token, config, client
                    )

                # Get user info
                user_info = await cls._get_platform_user_info(
                    platform, access_token, config["user_info_url"], client
                )
                
                if not user_info:
                    return {"success": False, "error": f"Failed to get user profile from {platform}"}

                # Save connection
                connection = await cls._save_connection(
                    db=db,
                    user_id=user_id,
                    platform=platform,
                    access_token=access_token,
                    refresh_token=token_data.get("refresh_token"),
                    expires_in=token_data.get("expires_in"),
                    platform_user_id=user_info.get("user_id"),
                    platform_username=user_info.get("username"),
                    platform_name=user_info.get("name"),
                    platform_email=user_info.get("email")
                )
                
                return {
                    "success": True,
                    "platform": platform,
                    "username": user_info.get("username") or user_info.get("name"),
                }
                
        except httpx.TimeoutException:
            return {"success": False, "error": f"Connection timeout with {platform}"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": "An unexpected error occurred"}

    @classmethod
    async def _exchange_long_lived_token(
        cls, platform: str, short_token: str, config: Dict, client: httpx.AsyncClient
    ) -> Tuple[str, Dict]:
        """Exchange short-lived token for long-lived token (Facebook/Instagram)"""
        try:
            exchange_url = "https://graph.facebook.com/v20.0/oauth/access_token"
            params = {
                "grant_type": "fb_exchange_token",
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "fb_exchange_token": short_token
            }
            
            response = await client.get(exchange_url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Exchanged for long-lived token for {platform}")
                return data["access_token"], data
            else:
                print(f"⚠️ Token exchange failed, using short-lived token")
                return short_token, {"access_token": short_token, "expires_in": 3600}
                
        except Exception as e:
            print(f"⚠️ Token exchange error: {e}")
            return short_token, {"access_token": short_token, "expires_in": 3600}

    @classmethod
    async def refresh_access_token(
        cls, connection: models.SocialConnection, db: AsyncSession
    ) -> Optional[Dict]:
        """Refresh an expired access token"""
        platform = connection.platform.lower()
        refresh_token = connection.refresh_token

        if not refresh_token:
            print(f"⚠️ No refresh token for {platform}")
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

            if config.get("token_auth_method") != "basic":
                refresh_params["client_secret"] = config["client_secret"]

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
            
            auth = None
            if config.get("token_auth_method") == "basic":
                auth = (config["client_id"], config["client_secret"])

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    config["token_url"],
                    data=refresh_params,
                    headers=headers,
                    auth=auth
                )
                
                if response.status_code != 200:
                    print(f"❌ Token refresh failed: {response.status_code}")
                    connection.is_active = False
                    await db.commit()
                    return None
                
                token_data = response.json()
                new_access_token = token_data.get("access_token")
                new_refresh_token = token_data.get("refresh_token", refresh_token)
                expires_in = token_data.get("expires_in")
                
                if not new_access_token:
                    return None
                
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
                
                print(f"✅ Token refreshed for {platform}")
                
                return {
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token,
                    "expires_in": expires_in
                }
                
        except Exception as e:
            print(f"❌ Token refresh error: {e}")
            return None

    @classmethod
    async def _get_platform_user_info(
        cls, platform: str, access_token: str, user_info_url: str, client: httpx.AsyncClient
    ) -> Optional[Dict]:
        """Get user info from platform API"""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.get(user_info_url, headers=headers)
            
            if response.status_code != 200:
                print(f"❌ User info error: {response.status_code}")
                return None

            data = response.json()
            
            if platform == "twitter":
                user_data = data.get("data", {})
                return {
                    "user_id": user_data.get("id"),
                    "username": user_data.get("username"),
                    "name": user_data.get("name")
                }
            elif platform in ["facebook", "instagram"]:
                return {
                    "user_id": data.get("id"),
                    "username": data.get("name"),
                    "name": data.get("name"),
                    "email": data.get("email")
                }
            elif platform in ["google", "youtube"]:
                return {
                    "user_id": data.get("sub"),
                    "username": data.get("email"),
                    "name": data.get("name"),
                    "email": data.get("email")
                }
                
        except Exception as e:
            print(f"❌ Error getting user info: {e}")
            return None
        
        return None

    @classmethod
    async def _save_connection(
        cls, db: AsyncSession, user_id: int, platform: str, access_token: str,
        refresh_token: Optional[str], expires_in: Optional[int], platform_user_id: Optional[str],
        platform_username: Optional[str] = None, platform_name: Optional[str] = None,
        platform_email: Optional[str] = None
    ) -> models.SocialConnection:
        
        if not platform_user_id:
            raise ValueError(f"platform_user_id required for {platform}")
        
        platform_username = platform_username or platform_name or platform_user_id
        
        result = await db.execute(
            select(models.SocialConnection).where(
                models.SocialConnection.user_id == user_id,
                models.SocialConnection.platform == platform.upper(),
                models.SocialConnection.platform_user_id == platform_user_id
            )
        )
        connection = result.scalar_one_or_none()
        
        expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in)) if expires_in else None
        
        if connection:
            connection.platform_username = platform_username
            connection.username = platform_name or platform_username
            connection.access_token = access_token
            connection.refresh_token = refresh_token
            connection.token_expires_at = expires_at
            connection.is_active = True
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
                updated_at=datetime.utcnow()
            )
            db.add(connection)
        
        await db.commit()
        await db.refresh(connection)
        return connection