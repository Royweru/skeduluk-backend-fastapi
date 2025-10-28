import secrets
import hashlib
import base64
from typing import Dict, Optional
from datetime import datetime, timedelta
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from app import models

# Import your models and settings
# from app import models, settings


class OAuthService:
    """Enhanced OAuth Service with proper PKCE implementation for Twitter"""
    
    # Store PKCE verifiers temporarily (use Redis in production)
    _pkce_verifiers: Dict[str, Dict] = {}
    
    OAUTH_CONFIGS = {
        "twitter": {
            "client_id": "YOUR_TWITTER_CLIENT_ID",
            "client_secret": "YOUR_TWITTER_CLIENT_SECRET",  # Optional for public clients
            "auth_url": "https://twitter.com/i/oauth2/authorize",
            "token_url": "https://api.twitter.com/2/oauth2/token",
            "revoke_url": "https://api.twitter.com/2/oauth2/revoke",
            "redirect_uri": "http://localhost:8000/auth/oauth/twitter/callback",
            "scope": "tweet.read tweet.write users.read follows.read follows.write offline.access",
        },
        # ... other platforms
    }
    
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
        Initiate OAuth flow with proper PKCE implementation
        Returns the authorization URL to redirect user to
        """
        platform = platform.lower()
        
        if platform not in cls.OAUTH_CONFIGS:
            raise ValueError(f"Unsupported platform: {platform}")
        
        config = cls.OAUTH_CONFIGS[platform]
        
        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Store user_id with state
        state_with_user = f"{user_id}:{state}"
        
        if platform == "twitter":
            # Generate PKCE parameters
            code_verifier = cls._generate_code_verifier()
            code_challenge = cls._generate_code_challenge(code_verifier)
            
            # Store verifier for later use (use Redis in production with TTL)
            cls._pkce_verifiers[state_with_user] = {
                "code_verifier": code_verifier,
                "timestamp": datetime.utcnow(),
                "user_id": user_id
            }
            
            # Build authorization URL with proper PKCE
            params = {
                "response_type": "code",
                "client_id": config["client_id"],
                "redirect_uri": config["redirect_uri"],
                "scope": config["scope"],
                "state": state_with_user,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256"
            }
            
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            auth_url = f"{config['auth_url']}?{query_string}"
            
            return auth_url
        
        # For other platforms, use the original implementation
        # ... (keep your existing code for other platforms)
    
    @classmethod
    async def handle_oauth_callback(
        cls, 
        platform: str, 
        code: str, 
        state: str,
        db: AsyncSession
    ) -> Dict:
        """
        Handle OAuth callback and exchange code for access token with PKCE
        """
        platform = platform.lower()
        
        if platform not in cls.OAUTH_CONFIGS:
            return {"success": False, "error": "Unsupported platform"}
        
        config = cls.OAUTH_CONFIGS[platform]
        
        # Extract user_id from state
        try:
            user_id = int(state.split(":")[0])
        except:
            return {"success": False, "error": "Invalid state parameter"}
        
        try:
            async with httpx.AsyncClient() as client:
                if platform == "twitter":
                    # Retrieve the code_verifier for this state
                    pkce_data = cls._pkce_verifiers.get(state)
                    
                    if not pkce_data:
                        return {
                            "success": False, 
                            "error": "PKCE verifier not found or expired"
                        }
                    
                    code_verifier = pkce_data["code_verifier"]
                    
                    # Prepare token request with PKCE
                    token_params = {
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": config["redirect_uri"],
                        "code_verifier": code_verifier,
                        "client_id": config["client_id"],
                    }
                    
                    # Add client_secret if using confidential client
                    if config.get("client_secret"):
                        token_params["client_secret"] = config["client_secret"]
                    
                    token_response = await client.post(
                        config["token_url"],
                        data=token_params,
                        headers={"Content-Type": "application/x-www-form-urlencoded"}
                    )
                    
                    # Clean up used verifier
                    cls._pkce_verifiers.pop(state, None)
                    
                else:
                    # Handle other platforms
                    token_params = {
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": config["redirect_uri"],
                        "client_id": config["client_id"],
                        "client_secret": config["client_secret"]
                    }
                    
                    if platform == "tiktok":
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
                    return {"success": False, "error": "No access token received"}
                
                # Get user profile from platform
                user_info = await cls._get_platform_user_info(platform, access_token)
                
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
                    platform_name=user_info.get("name")
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
        platform: str,
        refresh_token: str,
        db: AsyncSession,
        connection_id: int
    ) -> Optional[Dict]:
        """Refresh an expired access token"""
        platform = platform.lower()
        
        if platform not in cls.OAUTH_CONFIGS:
            return None
        
        config = cls.OAUTH_CONFIGS[platform]
        
        try:
            async with httpx.AsyncClient() as client:
                refresh_params = {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": config["client_id"],
                }
                
                if config.get("client_secret"):
                    refresh_params["client_secret"] = config["client_secret"]
                
                response = await client.post(
                    config["token_url"],
                    data=refresh_params,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code != 200:
                    print(f"Token refresh failed: {response.status_code} - {response.text}")
                    return None
                
                token_data = response.json()
                new_access_token = token_data.get("access_token")
                new_refresh_token = token_data.get("refresh_token", refresh_token)
                expires_in = token_data.get("expires_in")
                
                # Update connection in database
                result = await db.execute(
                    select(models.SocialConnection).where(
                        models.SocialConnection.id == connection_id
                    )
                )
                connection = result.scalar_one_or_none()
                
                if connection:
                    connection.access_token = new_access_token
                    connection.refresh_token = new_refresh_token
                    connection.token_expires_at = (
                        datetime.utcnow() + timedelta(seconds=expires_in)
                        if expires_in else None
                    )
                    connection.updated_at = datetime.utcnow()
                    await db.commit()
                
                return {
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token,
                    "expires_in": expires_in
                }
                
        except Exception as e:
            print(f"Token refresh error: {str(e)}")
            return None
    
    @classmethod
    async def _get_platform_user_info(cls, platform: str, access_token: str) -> Optional[Dict]:
        """Get user info from platform API"""
        try:
            async with httpx.AsyncClient() as client:
                if platform == "twitter":
                    # Use Twitter API v2 /users/me endpoint
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
                    else:
                        print(f"Twitter API error: {response.status_code} - {response.text}")
                
                # ... keep your existing code for other platforms
                
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
        platform_username: Optional[str] = None,
        platform_name: Optional[str] = None
    ) -> models.SocialConnection:
        """Save or update social connection"""
        
        # Ensure we have required fields
        if not platform_user_id:
            platform_user_id = f"temp_{platform}_{user_id}"
        
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
            connection.username = platform_name or platform_username
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
                username=platform_name or platform_username,
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


