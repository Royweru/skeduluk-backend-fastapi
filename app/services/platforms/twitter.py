# app/services/platforms/twitter.py
"""
Twitter/X platform service using OAuth 1.0a with API V2.
âœ… FIXED: Uses v2 media endpoint, proper error handling, prevents disconnections
"""

import httpx
from typing import Dict, List, Any, Optional
from requests_oauthlib import OAuth1Session
from io import BytesIO
import mimetypes
import asyncio
from .base_platform import BasePlatformService


class TwitterService(BasePlatformService):
    """Twitter/X platform service implementation"""
    
    PLATFORM_NAME = "TWITTER"
    MAX_IMAGES = 4
    MAX_VIDEOS = 1
    MAX_VIDEO_SIZE_MB = 512
    MAX_VIDEO_DURATION_SECONDS = 140
    
    # âœ… UPDATED: Use API V2 endpoints
    API_BASE = "https://api.twitter.com/2"
    
    # âœ… CRITICAL: Use new v2 media endpoint (v1.1 deprecated March 31, 2025)
    UPLOAD_BASE_V2 = "https://upload.twitter.com/2/media"  # New v2 endpoint
    UPLOAD_BASE_V1 = "https://upload.twitter.com/1.1"  # Fallback for compatibility
    
    @classmethod
    async def post(
        cls,
        access_token: str,
        content: str,
        image_urls: Optional[List[str]] = None,
        video_urls: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Post to Twitter using OAuth 1.0a with API V2.
        
        Args:
            access_token: Format "oauth_token:oauth_token_secret"
            content: Tweet text (max 280 chars)
            image_urls: List of image URLs (max 4)
            video_urls: List of video URLs (max 1)
        """
        print(f"🐦 Twitter: Starting tweet creation")
        
        # âœ… Validate token format
        if ':' not in access_token:
            error_msg = "Invalid token format. Expected 'oauth_token:oauth_secret'"
            print(f"âŒ Twitter: {error_msg}")
            return cls.format_error_response(error_msg)
        
        try:
            oauth_token, oauth_token_secret = access_token.split(':', 1)
        except Exception as e:
            return cls.format_error_response(f"Token parsing error: {e}")
        
        # Validate media
        error = cls.validate_media_count(image_urls, video_urls)
        if error:
            return cls.format_error_response(error)
        
        # Validate content length
        if len(content) > 280:
            return cls.format_error_response(
                f"Tweet too long: {len(content)} chars (max 280)"
            )
        
        try:
            from app.config import settings
            
            # âœ… Create OAuth1 session with proper credentials
            print(f"🐦 Twitter: Initializing OAuth 1.0a session")
            twitter = OAuth1Session(
                client_key=settings.TWITTER_API_KEY,
                client_secret=settings.TWITTER_API_SECRET,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret
            )
            
            # âœ… STEP 1: Upload media if present
            media_ids = []
            
            if image_urls:
                print(f"🐦 Twitter: Uploading {len(image_urls)} images")
                for idx, image_url in enumerate(image_urls[:cls.MAX_IMAGES], 1):
                    media_id = await cls._upload_media_v2(
                        twitter, image_url, "image", idx
                    )
                    if media_id:
                        media_ids.append(media_id)
                        print(f"   ✅ Image {idx} uploaded: {media_id}")
                    else:
                        print(f"   âš ï¸ Image {idx} upload failed, continuing...")
            
            if video_urls:
                print(f"🐦 Twitter: Uploading video")
                video_id = await cls._upload_media_v2(
                    twitter, video_urls[0], "video", 1
                )
                if video_id:
                    media_ids.append(video_id)
                    print(f"   ✅ Video uploaded: {video_id}")
                else:
                    print(f"   âš ï¸ Video upload failed, continuing...")
            
            # âœ… STEP 2: Create tweet
            tweet_data = {"text": content}
            
            if media_ids:
                tweet_data["media"] = {"media_ids": media_ids}
                print(f"🐦 Twitter: Posting tweet with {len(media_ids)} media attachments")
            else:
                print(f"🐦 Twitter: Posting text-only tweet")
            
            # Post tweet
            response = twitter.post(
                f"{cls.API_BASE}/tweets",
                json=tweet_data,
                timeout=30
            )
            
            # âœ… IMPROVED: Better error handling
            if response.status_code == 201:
                data = response.json()
                tweet_id = data["data"]["id"]
                
                print(f"✅ Twitter: Tweet posted successfully!")
                print(f"   Tweet ID: {tweet_id}")
                
                return cls.format_success_response(
                    tweet_id,
                    f"https://twitter.com/user/status/{tweet_id}"
                )
            
            elif response.status_code == 401:
                error_data = response.json() if response.text else {}
                error_msg = cls._parse_error_message(error_data)
                print(f"âŒ Twitter: 401 Unauthorized - {error_msg}")
                
                # âœ… Don't disconnect user - might be temporary
                return cls.format_error_response(
                    f"Authentication failed: {error_msg}. "
                    "Please try reconnecting your Twitter account."
                )
            
            elif response.status_code == 403:
                error_data = response.json() if response.text else {}
                error_msg = cls._parse_error_message(error_data)
                print(f"âŒ Twitter: 403 Forbidden - {error_msg}")
                
                # Check for specific permission issues
                if "Read and write" in error_msg or "permission" in error_msg.lower():
                    return cls.format_error_response(
                        "Twitter app lacks 'Read and Write' permissions. "
                        "Please check your Twitter Developer Portal settings."
                    )
                
                return cls.format_error_response(f"Forbidden: {error_msg}")
            
            elif response.status_code == 429:
                print(f"âŒ Twitter: 429 Rate Limit Exceeded")
                return cls.format_error_response(
                    "Twitter API rate limit exceeded. Please wait a few minutes and try again."
                )
            
            else:
                error_data = response.json() if response.text else {}
                error_msg = cls._parse_error_message(error_data)
                print(f"âŒ Twitter: Error {response.status_code} - {error_msg}")
                
                return cls.format_error_response(
                    f"Tweet failed ({response.status_code}): {error_msg}"
                )
                
        except Exception as e:
            print(f"âŒ Twitter post error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(f"Unexpected error: {str(e)}")
    
    @classmethod
    def _parse_error_message(cls, error_data: Dict) -> str:
        """Parse X API error response"""
        if not error_data:
            return "Unknown error"
        
        # V2 API error format
        if "detail" in error_data:
            return error_data["detail"]
        
        if "title" in error_data:
            title = error_data["title"]
            detail = error_data.get("detail", "")
            return f"{title}: {detail}" if detail else title
        
        # V1.1 API error format
        if "errors" in error_data:
            errors = error_data["errors"]
            if isinstance(errors, list) and errors:
                first_error = errors[0]
                return first_error.get("message", str(first_error))
        
        return str(error_data)
    
    @classmethod
    async def _upload_media_v2(
        cls,
        twitter_session: OAuth1Session,
        media_url: str,
        media_type: str,
        index: int = 1
    ) -> Optional[str]:
        """
        âœ… UPDATED: Upload media using v2 endpoint with v1.1 fallback
        """
        try:
            # Download media
            print(f"   📥 Downloading {media_type} {index}...")
            media_data = await cls.download_media(media_url, timeout=120)
            if not media_data:
                print(f"   âŒ Failed to download {media_type}")
                return None
            
            media_size_mb = len(media_data) / (1024 * 1024)
            print(f"   📦 {media_type.capitalize()} size: {media_size_mb:.2f}MB")
            
            # Determine content type
            content_type = mimetypes.guess_type(media_url)[0]
            if not content_type:
                content_type = "image/jpeg" if media_type == "image" else "video/mp4"
            
            # âœ… Try v2 endpoint first (future-proof)
            media_id = await cls._try_upload_v2(
                twitter_session, media_data, media_type, content_type
            )
            
            if media_id:
                return media_id
            
            # âœ… Fallback to v1.1 endpoint (for compatibility)
            print(f" ðŸ”„ Falling back to v1.1 endpoint...")
            media_id = await cls._try_upload_v1(
                twitter_session, media_data, media_type, content_type
            )
            
            return media_id
                
        except Exception as e:
            print(f"   âŒ Media upload error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @classmethod
    async def _try_upload_v2(
        cls,
        twitter_session: OAuth1Session,
        media_data: bytes,
        media_type: str,
        content_type: str
    ) -> Optional[str]:
        """Try uploading to v2 endpoint"""
        try:
            print(f"   📤 Trying v2 upload endpoint...")
            
            # Use multipart form data
            files = {
                "media": (
                    f"{media_type}.{content_type.split('/')[-1]}", 
                    BytesIO(media_data), 
                    content_type
                )
            }
            
            response = twitter_session.post(
                f"{cls.UPLOAD_BASE_V2}/upload",
                files=files,
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("media_id_string")
            
            print(f"   ⚠️ V2 upload failed: {response.status_code}")
            return None
            
        except Exception as e:
            print(f"   ⚠️ V2 upload exception: {e}")
            return None
    
    @classmethod
    async def _try_upload_v1(
        cls,
        twitter_session: OAuth1Session,
        media_data: bytes,
        media_type: str,
        content_type: str
    ) -> Optional[str]:
        """Fallback to v1.1 endpoint"""
        try:
            print(f"   📤 Using v1.1 upload endpoint...")
            
            files = {
                "media": (
                    f"{media_type}.{content_type.split('/')[-1]}", 
                    BytesIO(media_data), 
                    content_type
                )
            }
            
            response = twitter_session.post(
                f"{cls.UPLOAD_BASE_V1}/media/upload.json",
                files=files,
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("media_id_string")
            else:
                print(f"   âŒ V1.1 upload failed: {response.status_code}")
                print(f"   âŒ Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"   âŒ V1.1 upload exception: {e}")
            return None
    
    @classmethod
    async def validate_token(cls, access_token: str) -> bool:
        """
        âœ… IMPROVED: Validate Twitter OAuth tokens without causing disconnection
        """
        try:
            if ':' not in access_token:
                print(f"🐦 Twitter: Invalid token format")
                return False
            
            from app.config import settings
            oauth_token, oauth_token_secret = access_token.split(':', 1)
            
            twitter = OAuth1Session(
                client_key=settings.TWITTER_API_KEY,
                client_secret=settings.TWITTER_API_SECRET,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret
            )
            
            # âœ… Use v2 /users/me endpoint (lightweight)
            response = twitter.get(
                f"{cls.API_BASE}/users/me",
                timeout=10
            )
            
            is_valid = response.status_code == 200
            
            if not is_valid:
                print(f"🐦 Twitter: Token validation failed - {response.status_code}")
                print(f"   Response: {response.text[:200]}")
            
            return is_valid
            
        except Exception as e:
            print(f"🐦 Twitter: Token validation error - {e}")
            return False
    
    async def fetch_post_metrics(self, platform_post_id: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.twitter.com/2/tweets/{platform_post_id}?tweet.fields=public_metrics",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()["data"]["public_metrics"]
                return {
                    "likes": data["like_count"],
                    "retweets": data["retweet_count"],
                    "replies": data["reply_count"],
                    "quotes": data["quote_count"],
                    "impressions": data.get("impression_count", 0)
                }
            else:
                raise Exception(f"Failed to fetch metrics: {response.text}")