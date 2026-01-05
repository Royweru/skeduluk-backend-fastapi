# app/services/platforms/twitter.py
"""
Twitter/X platform service using OAuth 1.0a.
Note: Twitter requires OAuth 1.0a (NOT Bearer tokens) for posting.
"""

import httpx
from typing import Dict, List, Any, Optional
from requests_oauthlib import OAuth1Session
from io import BytesIO
import mimetypes
from .base_platform import BasePlatformService


class TwitterService(BasePlatformService):
    """Twitter/X platform service implementation"""
    
    PLATFORM_NAME = "TWITTER"
    MAX_IMAGES = 4
    MAX_VIDEOS = 1
    MAX_VIDEO_SIZE_MB = 512
    MAX_VIDEO_DURATION_SECONDS = 140
    
    API_BASE = "https://api.twitter.com/2"
    UPLOAD_BASE = "https://upload.twitter.com/1.1"
    
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
        Post to Twitter using OAuth 1.0a.
        
        Args:
            access_token: Format "oauth_token:oauth_token_secret"
            content: Tweet text (max 280 chars)
            image_urls: List of image URLs (max 4)
            video_urls: List of video URLs (max 1)
        """
        print(f"🐦 Twitter: Starting tweet creation")
        
        # Parse OAuth tokens
        if ':' not in access_token:
            return cls.format_error_response(
                "Invalid token format. Expected 'oauth_token:oauth_secret'"
            )
        
        oauth_token, oauth_token_secret = access_token.split(':', 1)
        
        # Validate media
        error = cls.validate_media_count(image_urls, video_urls)
        if error:
            return cls.format_error_response(error)
        
        try:
            from app.config import settings
            
            # Create OAuth1 session
            twitter = OAuth1Session(
                client_key=settings.TWITTER_API_KEY,
                client_secret=settings.TWITTER_API_SECRET,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret
            )
            
            tweet_data = {"text": content}
            media_ids = []
            
            # Upload images
            if image_urls:
                for image_url in image_urls[:cls.MAX_IMAGES]:
                    media_id = await cls._upload_media(twitter, image_url, "image")
                    if media_id:
                        media_ids.append(media_id)
            
            # Upload video (only 1 allowed)
            if video_urls:
                video_id = await cls._upload_media(twitter, video_urls[0], "video")
                if video_id:
                    media_ids.append(video_id)
            
            # Attach media
            if media_ids:
                tweet_data["media"] = {"media_ids": media_ids}
            
            # Post tweet
            print(f"🐦 Twitter: Posting tweet...")
            response = twitter.post(
                f"{cls.API_BASE}/tweets",
                json=tweet_data
            )
            
            if response.status_code == 201:
                data = response.json()
                tweet_id = data["data"]["id"]
                print(f"✅ Twitter: Tweet posted successfully")
                
                return cls.format_success_response(
                    tweet_id,
                    f"https://twitter.com/user/status/{tweet_id}"
                )
            else:
                return cls.format_error_response(
                    f"Tweet failed: {response.text}"
                )
                
        except Exception as e:
            print(f"❌ Twitter post error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
    @classmethod
    async def _upload_media(
        cls,
        twitter_session: OAuth1Session,
        media_url: str,
        media_type: str
    ) -> Optional[str]:
        """Upload media to Twitter and return media_id_string"""
        try:
            # Download media
            media_data = await cls.download_media(media_url, timeout=120)
            if not media_data:
                return None
            
            # Determine content type
            content_type = mimetypes.guess_type(media_url)[0] or "image/jpeg"
            
            # Upload
            files = {"media": (f"{media_type}.jpg", BytesIO(media_data), content_type)}
            response = twitter_session.post(
                f"{cls.UPLOAD_BASE}/media/upload.json",
                files=files
            )
            
            if response.status_code == 200:
                return response.json().get("media_id_string")
            else:
                print(f"❌ Twitter media upload failed: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Twitter media upload error: {e}")
            return None
    
    @classmethod
    async def validate_token(cls, access_token: str) -> bool:
        """Validate Twitter OAuth tokens"""
        try:
            if ':' not in access_token:
                return False
            
            from app.config import settings
            oauth_token, oauth_token_secret = access_token.split(':', 1)
            
            twitter = OAuth1Session(
                client_key=settings.TWITTER_API_KEY,
                client_secret=settings.TWITTER_API_SECRET,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret
            )
            
            response = twitter.get(f"{cls.API_BASE}/users/me")
            return response.status_code == 200
        except:
            return False