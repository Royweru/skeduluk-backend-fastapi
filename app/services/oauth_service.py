# app/services/oauth_service.py
import secrets
import hashlib
import base64
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode, quote, urlparse, urlunparse
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

# 🔧 IMPROVED: Better OAuth configurations with comments
# app/services/oauth_service.py

OAUTH_CONFIGS = {
    # ========================================================================
    # TWITTER - OAuth 1.0a (Three-Legged Flow)
    # ========================================================================
    "twitter": {
        "protocol": "oauth1",  
        "consumer_key": settings.TWITTER_API_KEY,
        "consumer_secret": settings.TWITTER_API_SECRET,
        "request_token_url": "https://api.twitter.com/oauth/request_token",
        "authorize_url": "https://api.twitter.com/oauth/authorize",
        "access_token_url": "https://api.twitter.com/oauth/access_token",
        "callback_uri": f"{BASE_URL}{CALLBACK_PATH}/twitter",
        "user_info_url": "https://api.twitter.com/2/users/me",
        "platform_display_name": "Twitter/X"
    },
    
    # ========================================================================
    # FACEBOOK - OAuth 2.0
    # ========================================================================
    "facebook": {
        "protocol": "oauth2",  
        "client_id": settings.FACEBOOK_APP_ID,
        "client_secret": settings.FACEBOOK_APP_SECRET,
        "auth_url": "https://www.facebook.com/v20.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v20.0/oauth/access_token",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/facebook",
        "scope": "public_profile,email,pages_show_list,pages_manage_posts",
        "user_info_url": "https://graph.facebook.com/v20.0/me?fields=id,name,email,picture",
        "uses_pkce": False,
        "token_auth_method": "body",
        "response_type": "code",
        "exchange_token": True,
        "auth_params": {"auth_type": "rerequest"},
        "platform_display_name": "Facebook"
    },
    
    # ========================================================================
    # INSTAGRAM - OAuth 2.0
    # ========================================================================
    "instagram": {
        "protocol": "oauth2",
        "client_id": settings.FACEBOOK_APP_ID,
        "client_secret": settings.FACEBOOK_APP_SECRET,
        "auth_url": "https://www.facebook.com/v20.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v20.0/oauth/access_token",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/instagram",
        "scope": "instagram_basic,pages_show_list,instagram_content_publish,business_management",
        "user_info_url": "https://graph.facebook.com/v20.0/me?fields=id,name,email,picture",
        "uses_pkce": False,
        "token_auth_method": "body",
        "response_type": "code",
        "exchange_token": True,
        "auth_params": {"auth_type": "rerequest"},
        "platform_display_name": "Instagram"
    },
    
    # ========================================================================
    # LINKEDIN - OAuth 2.0
    # ========================================================================
    "linkedin": {
        "protocol": "oauth2",
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/linkedin",
        "scope": "openid profile email w_member_social",
        "user_info_url": "https://api.linkedin.com/v2/userinfo",
        "uses_pkce": False,
        "token_auth_method": "body",
        "response_type": "code",
        "auth_params": {},
        "platform_display_name": "LinkedIn"
    },
    
    # ========================================================================
    # YOUTUBE (Google) - OAuth 2.0
    # ========================================================================
    "youtube": {
        "protocol": "oauth2",
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/youtube",
        "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/userinfo.profile",
        "user_info_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "uses_pkce": False,
        "token_auth_method": "body",
        "response_type": "code",
        "auth_params": {
            "access_type": "offline",
            "prompt": "consent"
        },
        "platform_display_name": "YouTube"
    },
    
    # ========================================================================
    # TIKTOK - OAuth 2.0 with PKCE
    # ========================================================================
    "tiktok": {
        "protocol": "oauth2",
        "client_id": settings.TIKTOK_CLIENT_ID,
        "client_secret": settings.TIKTOK_CLIENT_SECRET,
        "auth_url": "https://www.tiktok.com/v2/auth/authorize/",
        "token_url": "https://open.tiktok.com/v2/oauth/token/",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/tiktok",
        "scope": "user.info.basic,video.upload,video.publish",
        "user_info_url": "https://open.tiktok.com/v2/user/info/",
        "uses_pkce": True,
        "token_auth_method": "basic",
        "response_type": "code",
        "auth_params": {},
        "platform_display_name": "TikTok"
    }
}



class OAuthService:
    """OAuth Service with improved PKCE and state management"""
    """
    Universal OAuth service supporting both OAuth 1.0a and OAuth 2.0.
    
    Architecture:
    - Twitter uses OAuth 1.0a (three-legged flow)
    - All other platforms use OAuth 2.0 (authorization code flow)
    - Service intelligently routes based on `protocol` field in config
    """
    
    # ========================================================================
    # MAIN ENTRY POINTS
    # ========================================================================
    
    @classmethod
    async def initiate_oauth(cls, user_id: int, platform: str) -> str:
        """
        Main entry point for initiating OAuth flow.
        Routes to OAuth 1.0a or 2.0 based on platform configuration.
        """
        platform = platform.lower()
        
        if platform not in OAUTH_CONFIGS:
            raise HTTPException(500, f"Platform {platform} not configured")
        
        config = OAUTH_CONFIGS[platform]
        protocol = config.get("protocol", "oauth2")
        
        print(f"\n{'='*60}")
        print(f"🚀 Initiating {protocol.upper()} flow for {platform.upper()}")
        print(f"{'='*60}\n")
        
        if protocol == "oauth1":
            return await cls._initiate_oauth1(user_id, platform, config)
        else:
            return await cls._initiate_oauth2(user_id, platform, config)
    
    @classmethod
    async def handle_oauth_callback(
        cls, platform: str, 
        code: Optional[str], state: str,
        oauth_token: Optional[str], oauth_verifier: Optional[str],
        db: AsyncSession, error: Optional[str] = None
    ) -> Dict:
        """
        Main entry point for handling OAuth callbacks.
        Routes to OAuth 1.0a or 2.0 based on parameters received.
        """
        if error:
            return {"success": False, "error": f"Authorization denied: {error}"}
        
        platform = platform.lower()
        if platform not in OAUTH_CONFIGS:
            return {"success": False, "error": f"Unsupported platform: {platform}"}
        
        config = OAUTH_CONFIGS[platform]
        
        # Determine protocol based on parameters
        is_oauth1 = bool(oauth_token and oauth_verifier)
        is_oauth2 = bool(code)
        
        print(f"\n{'='*60}")
        print(f"📥 OAuth Callback - {platform.upper()}")
        print(f"OAuth 1.0a params: {is_oauth1}")
        print(f"OAuth 2.0 params: {is_oauth2}")
        print(f"{'='*60}\n")
        
        if is_oauth1:
            return await cls._handle_oauth1_callback(
                platform, oauth_token, oauth_verifier, state, config, db
            )
        elif is_oauth2:
            return await cls._handle_oauth2_callback(
                platform, code, state, config, db
            )
        else:
            return {
                "success": False,
                "error": "Missing required OAuth parameters"
            }
    
    # ========================================================================
    # OAUTH 1.0a IMPLEMENTATION (TWITTER)
    # ========================================================================
    
    @classmethod
    async def _initiate_oauth1(cls, user_id: int, platform: str, config: Dict) -> str:
        """OAuth 1.0a Three-Legged Flow - Step 1 & 2"""
        try:
            from requests_oauthlib import OAuth1Session
            
            # Step 1: Create OAuth1 session
            oauth = OAuth1Session(
                config["consumer_key"],
                client_secret=config["consumer_secret"],
                callback_uri=config["callback_uri"]
            )
            
            # Step 2: Get request token
            fetch_response = oauth.fetch_request_token(config["request_token_url"])
            oauth_token = fetch_response.get('oauth_token')
            oauth_token_secret = fetch_response.get('oauth_token_secret')
            
            if not oauth_token or not oauth_token_secret:
                raise HTTPException(500, "Failed to get request token")
            
            # Step 3: Store request token secret in state JWT
            state_payload = {
                "user_id": user_id,
                "platform": platform,
                "oauth_token": oauth_token,
                "oauth_token_secret": oauth_token_secret,
                "exp": datetime.utcnow() + timedelta(minutes=15)
            }
            state_jwt = jwt.encode(state_payload, settings.SECRET_KEY, algorithm="HS256")
            
            # Step 4: Build authorization URL
            authorization_url = oauth.authorization_url(config["authorize_url"])
            
            # Add state parameter
            parsed = urlparse(authorization_url)
            params = parse_qs(parsed.query)
            params['state'] = [state_jwt]
            new_query = urlencode(params, doseq=True)
            authorization_url = urlunparse((
                parsed.scheme, parsed.netloc, parsed.path,
                parsed.params, new_query, parsed.fragment
            ))
            
            print(f"✅ OAuth 1.0a authorization URL generated")
            return authorization_url
            
        except Exception as e:
            print(f"❌ OAuth 1.0a error: {e}")
            raise HTTPException(500, f"Failed to initiate OAuth: {str(e)}")
    
    @classmethod
    async def _handle_oauth1_callback(
        cls, platform: str, oauth_token: str, oauth_verifier: str,
        state: str, config: Dict, db: AsyncSession
    ) -> Dict:
        """OAuth 1.0a Three-Legged Flow - Step 3"""
        try:
            from requests_oauthlib import OAuth1Session
            
            # Decode state
            state_payload = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = state_payload["user_id"]
            oauth_token_secret = state_payload["oauth_token_secret"]
            
            # Exchange for access token
            oauth = OAuth1Session(
                config["consumer_key"],
                client_secret=config["consumer_secret"],
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret,
                verifier=oauth_verifier
            )
            
            oauth_tokens = oauth.fetch_access_token(config["access_token_url"])
            access_token = oauth_tokens.get('oauth_token')
            access_token_secret = oauth_tokens.get('oauth_token_secret')
            
            if not access_token or not access_token_secret:
                return {"success": False, "error": "Failed to get access tokens"}
            
            # ✅ CRITICAL: Format as "token:secret" for TwitterService
            combined_token = f"{access_token}:{access_token_secret}"
            
            # Get user info
            oauth_for_api = OAuth1Session(
                config["consumer_key"],
                client_secret=config["consumer_secret"],
                resource_owner_key=access_token,
                resource_owner_secret=access_token_secret
            )
            
            user_response = oauth_for_api.get(config["user_info_url"], timeout=10)
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                if "data" in user_data:
                    user_info = {
                        "user_id": user_data["data"]["id"],
                        "username": user_data["data"]["username"],
                        "name": user_data["data"]["name"]
                    }
                else:
                    user_info = {
                        "user_id": str(oauth_tokens.get("user_id", "")),
                        "username": oauth_tokens.get("screen_name", ""),
                        "name": oauth_tokens.get("screen_name", "")
                    }
            else:
                user_info = {
                    "user_id": str(oauth_tokens.get("user_id", "")),
                    "username": oauth_tokens.get("screen_name", "Unknown"),
                    "name": oauth_tokens.get("screen_name", "Unknown")
                }
            
            # Save connection
            connection = await cls._save_connection(
                db=db,
                user_id=user_id,
                platform=platform.upper(),
                access_token=combined_token,  # ✅ "token:secret" format
                refresh_token=None,  # OAuth 1.0a doesn't use refresh tokens
                expires_in=None,  # OAuth 1.0a tokens don't expire
                platform_user_id=user_info["user_id"],
                platform_username=user_info["username"],
                platform_name=user_info["name"]
            )
            
            print(f"✅ OAuth 1.0a connection saved")
            
            return {
                "success": True,
                "platform": platform,
                "username": user_info["username"]
            }
            
        except JWTError:
            return {"success": False, "error": "Invalid or expired connection link"}
        except Exception as e:
            print(f"❌ OAuth 1.0a callback error: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    # ========================================================================
    # OAUTH 2.0 IMPLEMENTATION (ALL OTHER PLATFORMS)
    # ========================================================================
    
    @classmethod
    async def _initiate_oauth2(cls, user_id: int, platform: str, config: Dict) -> str:
        """OAuth 2.0 Authorization Code Flow - Step 1"""
        try:
            # Generate state
            state = secrets.token_urlsafe(16)
            state_payload = {
                "user_id": user_id,
                "platform": platform,
                "state": state,
                "exp": datetime.utcnow() + timedelta(minutes=15)
            }
            
            # Build parameters
            params = {
                "response_type": config.get("response_type", "code"),
                "client_id": config["client_id"],
                "redirect_uri": config["redirect_uri"],
                "state": state
            }
            
            if config.get("scope"):
                params["scope"] = config["scope"]
            
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
            
            # Encode state
            state_jwt = jwt.encode(state_payload, settings.SECRET_KEY, algorithm="HS256")
            params["state"] = state_jwt
            
            # Build URL
            query_string = urlencode(params, quote_via=quote)
            auth_url = f"{config['auth_url']}?{query_string}"
            
            print(f"✅ OAuth 2.0 authorization URL generated")
            return auth_url
            
        except Exception as e:
            print(f"❌ OAuth 2.0 error: {e}")
            raise HTTPException(500, f"Failed to initiate OAuth: {str(e)}")
    
    @classmethod
    async def _handle_oauth2_callback(
        cls, platform: str, code: str, state: str,
        config: Dict, db: AsyncSession
    ) -> Dict:
        """OAuth 2.0 Authorization Code Flow - Step 2"""
        try:
            # Decode state
            state_payload = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = state_payload["user_id"]
            code_verifier = state_payload.get("pkce_verifier")
            
            # Build token request
            token_params = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config["redirect_uri"],
            }
            
            if config.get("token_auth_method") != "basic":
                token_params["client_id"] = config["client_id"]
                token_params["client_secret"] = config["client_secret"]
            
            if config.get("uses_pkce", False) and code_verifier:
                token_params["code_verifier"] = code_verifier
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
            
            auth = None
            if config.get("token_auth_method") == "basic":
                auth = (config["client_id"], config["client_secret"])
            
            # Exchange code for token
            async with httpx.AsyncClient(timeout=30.0) as client:
                token_response = await client.post(
                    config["token_url"],
                    data=token_params,
                    headers=headers,
                    auth=auth
                )
                
                if token_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Token exchange failed: {token_response.text}"
                    }
                
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
                    return {"success": False, "error": "Failed to get user profile"}
                
                # Save connection
                connection = await cls._save_connection(
                    db=db,
                    user_id=user_id,
                    platform=platform.upper(),
                    access_token=access_token,
                    refresh_token=token_data.get("refresh_token"),
                    expires_in=token_data.get("expires_in"),
                    platform_user_id=user_info.get("user_id"),
                    platform_username=user_info.get("username"),
                    platform_name=user_info.get("name"),
                    platform_email=user_info.get("email")
                )
                
                print(f"✅ OAuth 2.0 connection saved")
                
                return {
                    "success": True,
                    "platform": platform,
                    "username": user_info.get("username") or user_info.get("name")
                }
                
        except JWTError:
            return {"success": False, "error": "Invalid or expired connection link"}
        except Exception as e:
            print(f"❌ OAuth 2.0 callback error: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    

    @staticmethod
    def _generate_code_verifier() -> str:
        """Generate code verifier for PKCE (43-128 characters)"""
        # Generate 43 character verifier (Twitter minimum)
        verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        print(f"🔐 Generated code verifier (length: {len(verifier)})")
        return verifier

    @staticmethod
    def _generate_code_challenge(verifier: str) -> str:
        """Generate code challenge from verifier using S256"""
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        challenge = base64.urlsafe_b64encode(
            digest).decode('utf-8').rstrip('=')
        print(f"🔐 Generated code challenge (length: {len(challenge)})")
        return challenge

    @staticmethod
    def _generate_state() -> str:
        """Generate secure random state (at least 6 characters)"""
        return secrets.token_urlsafe(16)

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
                print(f" Exchanged for long-lived token (expires in {data.get('expires_in', 'unknown')}s)")
                return data["access_token"], data
            else:
                print(f"⚠️ Token exchange failed ({response.status_code}), using short-lived token")
                print(f"Response: {response.text}")
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
            print(f"⚠️ Platform {platform} not in OAUTH_CONFIGS")
            return None
        
        config = OAUTH_CONFIGS[platform]
        
        # 🔍 DEBUG: Print what we're about to do
        print(f"🔄 Attempting token refresh for {platform}")
        print(f"   Refresh token length: {len(refresh_token)}")
        print(f"   Token URL: {config['token_url']}")
        print(f"   Client ID: {config['client_id'][:20]}...")
        
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
                
                print(f"   Response status: {response.status_code}")
                
                if response.status_code != 200:
                    print(f"Token refresh failed")
                    print(f"   Response body: {response.text}")
                    # Mark connection as inactive so user knows to reconnect
                    connection.is_active = False
                    await db.commit()
                    return None
                
                token_data = response.json()
                new_access_token = token_data.get("access_token")
                new_refresh_token = token_data.get("refresh_token", refresh_token)
                expires_in = token_data.get("expires_in")
                
                if not new_access_token:
                    print(f" No access_token in response")
                    return None
                
                # Update connection
                connection.access_token = new_access_token
                connection.refresh_token = new_refresh_token
                connection.token_expires_at = (
                    datetime.utcnow() + timedelta(seconds=int(expires_in))
                    if expires_in else None
                )
                connection.updated_at = datetime.utcnow()
                connection.last_synced = datetime.utcnow()
                connection.is_active = True
                await db.commit()
                
                print(f" Token refreshed successfully!")
                print(f"   New expiry: {connection.token_expires_at}")
                print(f"   Days until expiry: {(connection.token_expires_at - datetime.utcnow()).days}")
                
                return {
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token,
                    "expires_in": expires_in
                }
                
        except Exception as e:
            print(f" Token refresh exception: {e}")
            import traceback
            traceback.print_exc()
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
                print(f" User info error: {response.status_code}")
                print(f"Response: {response.text}")
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
            elif platform == "linkedin":
                return {
                    "user_id": data.get("sub"),
                    "username": data.get("email"),
                    "name": data.get("name"),
                    "email": data.get("email")
                }
            #  ✅ TIKTOK USER INFO PARSING
            elif platform == "tiktok":
                # TikTok returns nested data structure
                user_data = data.get("data", {}).get("user", {})
                return {
                    "user_id": user_data.get("open_id"),
                    "username": user_data.get("display_name"),
                    "name": user_data.get("display_name"),
                    "email": None  # TikTok doesn't provide email
                }

                
        except Exception as e:
            print(f" Error getting user info: {e}")
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
            print(f"Updating existing connection ID: {connection.id}")
            connection.platform_username = platform_username
            connection.username = platform_name or platform_username
            connection.access_token = access_token
            connection.refresh_token = refresh_token
            connection.token_expires_at = expires_at
            connection.is_active = True
            connection.updated_at = datetime.utcnow()
        else:
            print(f"Creating new connection for user {user_id}")
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
        
        #  AUTO-SELECT FACEBOOK PAGE
        if platform.lower() == "facebook":
            print(f"🔵 Facebook connection detected - fetching pages...")
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    pages_response = await client.get(
                        "https://graph.facebook.com/v20.0/me/accounts",
                        params={
                            "access_token": access_token,
                            "fields": "id,name,category,access_token,picture"
                        }
                    )
                    
                    if pages_response.status_code == 200:
                        pages_data = pages_response.json()
                        pages = pages_data.get("data", [])
                        
                        if pages:
                            # Auto-select first page
                            first_page = pages[0]
                            
                            connection.facebook_page_id = first_page["id"]
                            connection.facebook_page_name = first_page["name"]
                            connection.facebook_page_access_token = first_page["access_token"]
                            connection.facebook_page_category = first_page.get("category", "Unknown")
                            
                            # Get page picture URL
                            picture_data = first_page.get("picture", {})
                            if isinstance(picture_data, dict):
                                picture_url = picture_data.get("data", {}).get("url")
                            else:
                                picture_url = None
                            connection.facebook_page_picture = picture_url
                            
                            print(f" Auto-selected Facebook Page: {first_page['name']} (ID: {first_page['id']})")
                            print(f"   Category: {first_page.get('category', 'Unknown')}")
                            print(f"   Total pages available: {len(pages)}")
                            
                            if len(pages) > 1:
                                print(f"   ℹ️  User has {len(pages)} pages. They can change selection in settings.")
                        else:
                            print(f"⚠️  No Facebook Pages found for this user.")
                            print(f"   User needs to create a Facebook Page to post via API.")
                            # Clear any previous page selection
                            connection.facebook_page_id = None
                            connection.facebook_page_name = None
                            connection.facebook_page_access_token = None
                            connection.facebook_page_category = None
                            connection.facebook_page_picture = None
                    else:
                        print(f"⚠️  Failed to fetch Facebook pages: {pages_response.status_code}")
                        print(f"   Response: {pages_response.text}")
                        # Don't fail the connection, just log the issue
                        
            except httpx.TimeoutException:
                print(f"⚠️  Timeout while fetching Facebook pages. Connection saved but no page selected.")
            except httpx.HTTPError as e:
                print(f"⚠️  HTTP error while fetching Facebook pages: {e}")
            except Exception as e:
                print(f"⚠️  Unexpected error while fetching Facebook pages: {e}")
                import traceback
                traceback.print_exc()
                # Don't fail the connection - user can select page later
        
        # Final commit and refresh
        await db.commit()
        await db.refresh(connection)
        
        return connection