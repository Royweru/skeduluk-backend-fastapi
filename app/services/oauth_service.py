import secrets
import hashlib
import base64
from typing import Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from jose import jwt, JWTError
from ..config import settings
from app import models

# --- OAuth Configuration ---
BASE_URL = settings.BACKEND_URL.rstrip("/")
CALLBACK_PATH = "/auth/oauth/callback"

# Global state storage for OAuth 1.0a
_oauth1_states = {}

def _clean_oauth1_states():
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    expired = [k for k, v in _oauth1_states.items() if v.get("created_at", datetime.utcnow()) < cutoff]
    for k in expired:
        del _oauth1_states[k]

OAUTH_CONFIGS = {
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
    "instagram": {
        "protocol": "oauth2",
        "client_id": settings.INSTAGRAM_CLIENT_ID or settings.FACEBOOK_APP_ID,
        "client_secret": settings.INSTAGRAM_CLIENT_SECRET or settings.FACEBOOK_APP_SECRET,
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
    "tiktok": {
        "protocol": "oauth2",
        "client_id": settings.TIKTOK_CLIENT_ID,
        "client_secret": settings.TIKTOK_CLIENT_SECRET,
        "auth_url": "https://www.tiktok.com/v2/auth/authorize/",
        # ⚠️ CRITICAL: Trailing slash is REQUIRED by TikTok V2
        "token_url": "https://open.tiktokapis.com/v2/oauth/token/", 
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/tiktok",
        "scope": "user.info.basic,video.upload,video.publish",
        "user_info_url": "https://open.tiktokapis.com/v2/user/info/", 
        "uses_pkce": True,
        "token_auth_method": "body", 
        "response_type": "code",
        "client_id_param_name": "client_key",  # TikTok uses client_key
        "auth_params": {},
        "platform_display_name": "TikTok"
    }
}

class OAuthService:
    @classmethod
    async def initiate_oauth(cls, user_id: int, platform: str) -> str:
        platform = platform.lower()
        if platform not in OAUTH_CONFIGS:
            raise HTTPException(500, f"Platform {platform} not configured")
        
        config = OAUTH_CONFIGS[platform]
        protocol = config.get("protocol", "oauth2")
        
        if protocol == "oauth1":
            return await cls._initiate_oauth1(user_id, platform, config)
        else:
            return await cls._initiate_oauth2(user_id, platform, config)
    
    @classmethod
    async def handle_oauth_callback(
        cls, platform: str, 
        code: Optional[str], state: Optional[str],
        oauth_token: Optional[str], oauth_verifier: Optional[str],
        db: AsyncSession, error: Optional[str] = None
    ) -> Dict:
        if error:
            return {"success": False, "error": f"Authorization denied: {error}"}
        
        platform = platform.lower()
        if platform not in OAUTH_CONFIGS:
            return {"success": False, "error": f"Unsupported platform: {platform}"}
        
        config = OAUTH_CONFIGS[platform]
        is_oauth1 = bool(oauth_token and oauth_verifier)
        is_oauth2 = bool(code)
        
        if is_oauth1:
            return await cls._handle_oauth1_callback(
                platform, oauth_token, oauth_verifier, config, db
            )
        elif is_oauth2:
            if not state:
                return {"success": False, "error": "Missing state parameter"}
            return await cls._handle_oauth2_callback(
                platform, code, state, config, db
            )
        else:
            return {"success": False, "error": "Missing required OAuth parameters"}
    
    # --- OAuth 1.0a (Twitter) ---
    @classmethod
    async def _initiate_oauth1(cls, user_id: int, platform: str, config: Dict) -> str:
        try:
            from requests_oauthlib import OAuth1Session
            oauth = OAuth1Session(
                config["consumer_key"],
                client_secret=config["consumer_secret"],
                callback_uri=config["callback_uri"]
            )
            fetch_response = oauth.fetch_request_token(config["request_token_url"])
            oauth_token = fetch_response.get('oauth_token')
            oauth_token_secret = fetch_response.get('oauth_token_secret')
            
            if not oauth_token: raise Exception("Failed to get request token")
            
            _clean_oauth1_states()  
            _oauth1_states[oauth_token] = {
                "user_id": user_id,
                "platform": platform,
                "oauth_token_secret": oauth_token_secret,
                "created_at": datetime.utcnow()
            }
            return oauth.authorization_url(config["authorize_url"])
        except Exception as e:
            raise HTTPException(500, f"Failed to initiate OAuth: {str(e)}")

    @classmethod
    async def _handle_oauth1_callback(cls, platform: str, oauth_token: str, oauth_verifier: str, config: Dict, db: AsyncSession) -> Dict:
        try:
            from requests_oauthlib import OAuth1Session
            state_data = _oauth1_states.get(oauth_token)
            if not state_data: return {"success": False, "error": "Invalid session"}
            del _oauth1_states[oauth_token]
            
            oauth = OAuth1Session(
                config["consumer_key"],
                client_secret=config["consumer_secret"],
                resource_owner_key=oauth_token,
                resource_owner_secret=state_data["oauth_token_secret"],
                verifier=oauth_verifier
            )
            tokens = oauth.fetch_access_token(config["access_token_url"])
            
            # Get User Info
            oauth_api = OAuth1Session(
                config["consumer_key"],
                client_secret=config["consumer_secret"],
                resource_owner_key=tokens['oauth_token'],
                resource_owner_secret=tokens['oauth_token_secret']
            )
            user_resp = oauth_api.get(config["user_info_url"])
            user_info = {"user_id": tokens.get("user_id"), "username": tokens.get("screen_name")}
            if user_resp.status_code == 200:
                d = user_resp.json().get("data", {})
                user_info = {"user_id": d.get("id"), "username": d.get("username"), "name": d.get("name")}
            
            await cls._save_connection(
                db=db, user_id=state_data["user_id"], platform=platform.upper(),
                access_token=f"{tokens['oauth_token']}:{tokens['oauth_token_secret']}",
                refresh_token=None, expires_in=None,
                platform_user_id=str(user_info["user_id"]),
                platform_username=user_info["username"],
                platform_name=user_info.get("name"),
                platform_protocol="oauth1",
                oauth_token_secret=tokens['oauth_token_secret']
            )
            return {"success": True, "platform": platform, "username": user_info["username"]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- OAuth 2.0 (The Fix) ---
    @classmethod
    async def _initiate_oauth2(cls, user_id: int, platform: str, config: Dict) -> str:
        try:
            state = secrets.token_urlsafe(16)
            state_payload = {"user_id": user_id, "platform": platform, "state": state, "exp": datetime.utcnow() + timedelta(minutes=15)}
            
            client_id_param_name = config.get("client_id_param_name", "client_id")
            params = {
                "response_type": config.get("response_type", "code"),
                client_id_param_name: config["client_id"],
                "redirect_uri": config["redirect_uri"],
                "state": state
            }
            if config.get("scope"): params["scope"] = config["scope"]
            params.update(config.get("auth_params", {}))
            
            if config.get("uses_pkce", False):
                code_verifier = cls._generate_code_verifier()
                params.update({"code_challenge": cls._generate_code_challenge(code_verifier), "code_challenge_method": "S256"})
                state_payload["pkce_verifier"] = code_verifier
            
            state_jwt = jwt.encode(state_payload, settings.SECRET_KEY, algorithm="HS256")
            params["state"] = state_jwt
            return f"{config['auth_url']}?{urlencode(params, quote_via=quote)}"
        except Exception as e:
            raise HTTPException(500, f"Failed to initiate OAuth: {str(e)}")

    @classmethod
    async def _handle_oauth2_callback(cls, platform: str, code: str, state: str, config: Dict, db: AsyncSession) -> Dict:
        try:
            state_payload = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = state_payload["user_id"]
            code_verifier = state_payload.get("pkce_verifier")
            
            client_id_param_name = config.get("client_id_param_name", "client_id")
            token_params = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config["redirect_uri"],
            }
            if config.get("token_auth_method") != "basic":
                token_params[client_id_param_name] = config["client_id"]
                token_params["client_secret"] = config["client_secret"]
            if config.get("uses_pkce", False) and code_verifier:
                token_params["code_verifier"] = code_verifier
            
            # ⚠️ CRITICAL FIX: Add User-Agent to bypass TikTok 404 TLB
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "SkedulukApp/1.0 (compatible; httpx/0.23.0)" 
            }
            
            auth = None
            if config.get("token_auth_method") == "basic":
                auth = (config["client_id"], config["client_secret"])
            
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                print(f"🔄 Exchanging code for token with {config['token_url']}")
                token_response = await client.post(
                    config["token_url"],
                    data=token_params,
                    headers=headers,
                    auth=auth
                )
                
                if token_response.status_code != 200:
                    print(f"❌ Token exchange failed: {token_response.status_code} - {token_response.text}")
                    return {"success": False, "error": f"Token exchange failed: {token_response.status_code}"}
                
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                
                if not access_token:
                    return {"success": False, "error": "No access token received"}
                
                # Exchange for long-lived (Facebook/IG)
                if config.get("exchange_token"):
                    access_token, token_data = await cls._exchange_long_lived_token(platform, access_token, config, client)
                
                # Get User Info
                user_info = await cls._get_platform_user_info(platform, access_token, config["user_info_url"], client)
                if not user_info:
                    return {"success": False, "error": "Failed to get user profile"}
                
                await cls._save_connection(
                    db=db, user_id=user_id, platform=platform.upper(),
                    access_token=access_token,
                    refresh_token=token_data.get("refresh_token"),
                    expires_in=token_data.get("expires_in"),
                    platform_user_id=str(user_info.get("user_id")),
                    platform_username=user_info.get("username"),
                    platform_name=user_info.get("name"),
                    platform_protocol=config.get("protocol")
                )
                return {"success": True, "platform": platform, "username": user_info.get("username")}
                
        except JWTError:
            return {"success": False, "error": "Invalid or expired connection link"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Helpers ---
    @staticmethod
    def _generate_code_verifier() -> str:
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

    @staticmethod
    def _generate_code_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

    @classmethod
    async def _exchange_long_lived_token(cls, platform: str, short_token: str, config: Dict, client: httpx.AsyncClient) -> Tuple[str, Dict]:
        try:
            if platform in ["facebook", "instagram"]:
                params = {"grant_type": "fb_exchange_token", "client_id": config["client_id"], "client_secret": config["client_secret"], "fb_exchange_token": short_token}
                resp = await client.get("https://graph.facebook.com/v20.0/oauth/access_token", params=params)
                if resp.status_code == 200: return resp.json()["access_token"], resp.json()
            return short_token, {}
        except: return short_token, {}

    @classmethod
    async def _get_platform_user_info(cls, platform: str, access_token: str, user_info_url: str, client: httpx.AsyncClient) -> Optional[Dict]:
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {}
            if platform == "tiktok":
                params = {"fields": "open_id,union_id,avatar_url,display_name"}
            
            resp = await client.get(user_info_url, headers=headers, params=params)
            if resp.status_code != 200: return None
            data = resp.json()
            
            if platform == "tiktok":
                u = data.get("data", {}).get("user", {})
                return {"user_id": u.get("open_id"), "username": u.get("display_name"), "name": u.get("display_name")}
            elif platform == "twitter":
                d = data.get("data", {})
                return {"user_id": d.get("id"), "username": d.get("username"), "name": d.get("name")}
            elif platform in ["facebook", "instagram", "linkedin", "google", "youtube"]:
                return {"user_id": data.get("id") or data.get("sub"), "username": data.get("name") or data.get("email"), "name": data.get("name")}
            return None
        except: return None

    @classmethod
    async def _save_connection(cls, db: AsyncSession, user_id: int, platform: str, access_token: str, refresh_token: Optional[str], expires_in: Optional[int], platform_user_id: Optional[str], platform_username: Optional[str] = None, platform_name: Optional[str] = None, platform_protocol:Optional[str] = None, oauth_token_secret:Optional[str] = None) -> models.SocialConnection:
        if not platform_user_id: raise ValueError(f"platform_user_id required for {platform}")
        
        result = await db.execute(select(models.SocialConnection).where(
            models.SocialConnection.user_id == user_id,
            models.SocialConnection.platform == platform.upper(),
            models.SocialConnection.platform_user_id == platform_user_id
        ))
        connection = result.scalar_one_or_none()
        expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in)) if expires_in else None
        
        if connection:
            connection.access_token = access_token
            connection.refresh_token = refresh_token
            connection.token_expires_at = expires_at
            connection.is_active = True
            connection.updated_at = datetime.utcnow()
        else:
            connection = models.SocialConnection(
                user_id=user_id, platform=platform.upper(), protocol=platform_protocol,
                platform_user_id=platform_user_id, platform_username=platform_username or platform_name,
                username=platform_name or platform_username, access_token=access_token,
                refresh_token=refresh_token, token_expires_at=expires_at, is_active=True
            )
            db.add(connection)
        
        await db.commit()
        await db.refresh(connection)
        return connection

    @classmethod
    async def refresh_access_token(cls, connection: models.SocialConnection, db: AsyncSession) -> bool:
        platform = connection.platform.lower()
        if not connection.refresh_token or platform not in OAUTH_CONFIGS: return False
        
        config = OAUTH_CONFIGS[platform]
        client_id_param = config.get("client_id_param_name", "client_id")
        
        params = {
            "grant_type": "refresh_token",
            "refresh_token": connection.refresh_token,
            client_id_param: config["client_id"]
        }
        if config.get("token_auth_method") != "basic":
            params["client_secret"] = config["client_secret"]
            
        headers = {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "SkedulukApp/1.0"}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(config["token_url"], data=params, headers=headers)
                if resp.status_code != 200: return False
                
                data = resp.json()
                connection.access_token = data.get("access_token")
                connection.refresh_token = data.get("refresh_token", connection.refresh_token)
                if data.get("expires_in"):
                    connection.token_expires_at = datetime.utcnow() + timedelta(seconds=int(data["expires_in"]))
                connection.last_synced = datetime.utcnow()
                await db.commit()
                return True
        except: return False