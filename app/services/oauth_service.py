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

# 🔧 IMPROVED: Better OAuth configurations with comments
# app/services/oauth_service.py

OAUTH_CONFIGS = {
    "twitter": {
        "client_id": settings.TWITTER_CLIENT_ID,
        "client_secret": settings.TWITTER_CLIENT_SECRET,
        "auth_url": "https://twitter.com/i/oauth2/authorize",
        "token_url": "https://api.twitter.com/2/oauth2/token",
        "revoke_url": "https://api.twitter.com/2/oauth2/revoke",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/twitter",
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
        "scope": "public_profile,email,pages_show_list",
        "user_info_url": "https://graph.facebook.com/v20.0/me?fields=id,name,email,picture",
        "uses_pkce": False,
        "token_auth_method": "body",
        "response_type": "code",
        "exchange_token": True,
        "auth_params": {
            "auth_type": "rerequest",
        }
    },
    "instagram": {
        "client_id": settings.FACEBOOK_APP_ID,
        "client_secret": settings.FACEBOOK_APP_SECRET,
        "auth_url": "https://www.facebook.com/v20.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v20.0/oauth/access_token",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/instagram",
        "scope": "instagram_basic,pages_show_list,business_management",
        "user_info_url": "https://graph.facebook.com/v20.0/me?fields=id,name,email,picture",
        "uses_pkce": False,
        "token_auth_method": "body",
        "response_type": "code",
        "exchange_token": True,
        "platform_display_name": "Instagram",
        "auth_params": {
            "auth_type": "rerequest",
        }
    },
    #  ADD LINKEDIN HERE
    "linkedin": {
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/linkedin",
        # Scopes: openid, profile, email for user info + w_member_social for posting
        "scope": "openid profile email w_member_social",
        "user_info_url": "https://api.linkedin.com/v2/userinfo",
        "uses_pkce": False,
        "token_auth_method": "body",  # LinkedIn uses body params, not Basic Auth
        "response_type": "code",
        "platform_display_name": "LinkedIn",
        "auth_params": {}
    },
    "youtube": {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "redirect_uri": f"{BASE_URL}{CALLBACK_PATH}/youtube",
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
    def validate_config(cls, platform: str) -> Tuple[bool, Optional[str]]:
        """Validate OAuth configuration for a platform"""
        if platform not in OAUTH_CONFIGS:
            return False, f"Platform '{platform}' not supported"

        config = OAUTH_CONFIGS[platform]

        # Check required fields
        if not config.get("client_id"):
            return False, f"Client ID not configured for {platform}"

        if not config.get("client_secret"):
            return False, f"Client Secret not configured for {platform}"

        if not config.get("redirect_uri"):
            return False, f"Redirect URI not configured for {platform}"

        # Validate redirect URI format
        redirect_uri = config["redirect_uri"]
        if not redirect_uri.startswith(("http://", "https://")):
            return False, f"Invalid redirect URI format: {redirect_uri}"

        return True, None

    @classmethod
    async def initiate_oauth(cls, user_id: int, platform: str) -> str:
        """Initiate OAuth flow with proper PKCE and state management"""
        platform = platform.lower()

        # Validate configuration
        is_valid, error_message = cls.validate_config(platform)
        if not is_valid:
            raise HTTPException(status_code=500, detail=error_message)

        config = OAUTH_CONFIGS[platform]

        print("\n" + "="*70)
        print(f"🚀 INITIATING OAUTH FOR {platform.upper()}")
        print("="*70)
        print(f"Client ID: {config['client_id'][:15]}..." if config.get(
            'client_id') else "Client ID: NOT SET")
        print(
            f"Client Secret: {'SET' if config.get('client_secret') else 'NOT SET'}")
        print(f"Redirect URI: {config['redirect_uri']}")
        print(f"Scopes: {config.get('scope', 'NONE')}")
        print(f"Uses PKCE: {config.get('uses_pkce', False)}")
        print("="*70 + "\n")

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
            print(
                f" PKCE enabled - Verifier length: {len(code_verifier)}, Challenge length: {len(code_challenge)}")

        # Encode the state payload into a JWT
        state_jwt = jwt.encode(
            state_payload, settings.SECRET_KEY, algorithm="HS256")
        params["state"] = state_jwt

        # Build authorization URL
        query_string = urlencode(params, quote_via=quote)
        auth_url = f"{config['auth_url']}?{query_string}"

        print(f"🔗 Generated OAuth URL (first 150 chars): {auth_url[:150]}...")
        print(f"📍 Full redirect will be to: {config['redirect_uri']}")
        print()

        return auth_url

    @classmethod
    async def handle_oauth_callback(
        cls, platform: str, code: str, state: str, db: AsyncSession, error: Optional[str] = None
    ) -> Dict:
        """Handle OAuth callback with proper error handling"""
        print("\n" + "="*70)
        print(f"📥 OAUTH CALLBACK RECEIVED FOR {platform.upper()}")
        print("="*70)
        
        if error:
            print(f" Error parameter present: {error}")
            return {"success": False, "error": f"Authorization denied: {error}"}

        platform = platform.lower()
        if platform not in OAUTH_CONFIGS:
            return {"success": False, "error": f"Unsupported platform: {platform}"}

        config = OAUTH_CONFIGS[platform]
        
        print(f"Code received (first 20 chars): {code[:20]}...")
        print(f"State received (first 30 chars): {state[:30]}...")

        # Decode and validate state JWT
        try:
            state_payload = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
            
            if state_payload.get("platform") != platform:
                raise JWTError("Platform mismatch in state token")
            
            user_id = state_payload["user_id"]
            code_verifier = state_payload.get("pkce_verifier")
            
            print(f" State validated - User ID: {user_id}")
            if code_verifier:
                print(f" PKCE verifier retrieved (length: {len(code_verifier)})")

        except JWTError as e:
            print(f" Invalid state token: {e}")
            return {"success": False, "error": "Invalid or expired connection link. Please try again."}

        try:
            #  FIXED: Build token params based on auth method
            token_params = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config["redirect_uri"],
            }
            
            #  FIX: Only add credentials to body if NOT using Basic Auth
            if config.get("token_auth_method") != "basic":
                token_params["client_id"] = config["client_id"]
                token_params["client_secret"] = config["client_secret"]
            
            # Add PKCE verifier if needed
            if config.get("uses_pkce", False):
                if not code_verifier:
                    return {"success": False, "error": "PKCE verifier missing from state."}
                token_params["code_verifier"] = code_verifier
                print(f" Adding PKCE verifier to token request (length: {len(code_verifier)})")

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
            
            # Set up authentication
            auth = None
            if config.get("token_auth_method") == "basic":
                #  For Basic Auth: credentials in header, NOT body
                auth = (config["client_id"], config["client_secret"])
                print(f" Using Basic Auth for token exchange (credentials in Authorization header)")
                print(f"   Client ID: {config['client_id'][:15]}...")
            else:
                print(f" Using body parameters for token exchange")

            print("\n" + "-"*70)
            print("🔄 EXCHANGING CODE FOR TOKEN")
            print("-"*70)
            print(f"Token URL: {config['token_url']}")
            print(f"Redirect URI: {config['redirect_uri']}")
            print(f"Grant Type: authorization_code")
            print(f"Auth Method: {config.get('token_auth_method', 'body')}")
            print(f"PKCE Enabled: {config.get('uses_pkce', False)}")
            print(f"Body Parameters: {list(token_params.keys())}")
            print("-"*70 + "\n")

            async with httpx.AsyncClient(timeout=30.0) as client:
                token_response = await client.post(
                    config["token_url"],
                    data=token_params,
                    headers=headers,
                    auth=auth
                )

                print(f"Token Response Status: {token_response.status_code}")
                
                if token_response.status_code != 200:
                    error_body = token_response.text
                    print(f" Token exchange failed!")
                    print(f"Status Code: {token_response.status_code}")
                    print(f"Response body: {error_body}")
                    
                    #  Enhanced debugging
                    print(f"\n🔍 DEBUG INFO:")
                    print(f"  Token URL: {config['token_url']}")
                    print(f"  Redirect URI sent: {config['redirect_uri']}")
                    print(f"  Client ID (first 15): {config['client_id'][:15]}...")
                    print(f"  Auth Method: {config.get('token_auth_method')}")
                    print(f"  Has Code Verifier: {bool(code_verifier)}")
                    if code_verifier:
                        print(f"  Code Verifier Length: {len(code_verifier)}")
                    print(f"  Body Params: {list(token_params.keys())}")
                    print("="*70 + "\n")
                    
                    # Try to parse error message
                    try:
                        error_data = token_response.json()
                        error_msg = error_data.get("error_description") or error_data.get("error") or error_body
                    except:
                        error_msg = error_body
                    
                    return {"success": False, "error": f"Token exchange failed: {error_msg[:200]}"}
                
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                
                if not access_token:
                    print(" No access token in response")
                    print(f"Response: {token_data}")
                    return {"success": False, "error": "No access token received"}
                
                print(f" Access token received (length: {len(access_token)})")
                print(f"Token expires in: {token_data.get('expires_in', 'unknown')} seconds")
                print(f"Refresh token: {'YES' if token_data.get('refresh_token') else 'NO'}")

                # Exchange for long-lived token (Facebook/Instagram)
                if config.get("exchange_token"):
                    print("\n🔄 Exchanging for long-lived token...")
                    access_token, token_data = await cls._exchange_long_lived_token(
                        platform, access_token, config, client
                    )

                # Get user info
                print("\n🔄 Fetching user info...")
                user_info = await cls._get_platform_user_info(
                    platform, access_token, config["user_info_url"], client
                )
                
                if not user_info:
                    print(" Failed to get user info")
                    return {"success": False, "error": f"Failed to get user profile from {platform}"}
                
                print(f" User info retrieved: {user_info.get('username') or user_info.get('name')}")

                # Save connection
                print("\n💾 Saving connection to database...")
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
                
                print(f" Connection saved with ID: {connection.id}")
                print("="*70 + "\n")
                
                return {
                    "success": True,
                    "platform": platform,
                    "username": user_info.get("username") or user_info.get("name"),
                }
                
        except httpx.TimeoutException:
            print(" Connection timeout")
            return {"success": False, "error": f"Connection timeout with {platform}"}
        except Exception as e:
            print(f" Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": f"An unexpected error occurred: {str(e)[:100]}"}

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
