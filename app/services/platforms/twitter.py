# app/services/platforms/twitter.py
"""
Twitter/X platform service using OAuth 1.0a with API V1.1 for media uploads.
✅ FIXED: Proper chunked upload for videos (INIT → APPEND → FINALIZE → STATUS)
✅ Uses v1.1 endpoint for media (reliable until March 31, 2025)
✅ Posts tweets using v2 API
"""

import httpx
from typing import Dict, List, Any, Optional
from requests_oauthlib import OAuth1Session
from io import BytesIO
import mimetypes
import asyncio
import time
import os
from .base_platform import BasePlatformService


class TwitterService(BasePlatformService):
    """Twitter/X platform service implementation with chunked video upload"""
    
    PLATFORM_NAME = "TWITTER"
    MAX_IMAGES = 4
    MAX_VIDEOS = 1
    MAX_VIDEO_SIZE_MB = 512
    MAX_VIDEO_DURATION_SECONDS = 140
    
    # API endpoints
    API_BASE = "https://api.twitter.com/2"
    UPLOAD_BASE = "https://upload.twitter.com/1.1"
    
    # Chunked upload settings
    CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunks (Twitter's max per chunk)
    MAX_UPLOAD_RETRIES = 3
    
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
        
        Returns:
            Dict with success status, platform_post_id, url, and error (if failed)
        """
        print(f"\n🐦 Twitter: Starting tweet creation")
        
        # ✅ Validate token format
        if ':' not in access_token:
            error_msg = "Invalid token format. Expected 'oauth_token:oauth_secret'"
            print(f"❌ Twitter: {error_msg}")
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
            
            # ✅ Create OAuth1 session
            print(f"🐦 Twitter: Initializing OAuth 1.0a session")
            twitter = OAuth1Session(
                client_key=settings.TWITTER_API_KEY,
                client_secret=settings.TWITTER_API_SECRET,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret
            )
            
            # ✅ STEP 1: Upload media if present
            media_ids = []
            
            # Upload images (simple upload)
            if image_urls:
                print(f"🐦 Twitter: Uploading {len(image_urls)} images")
                for idx, image_url in enumerate(image_urls[:cls.MAX_IMAGES], 1):
                    media_id = await cls._upload_image(twitter, image_url, idx)
                    if media_id:
                        media_ids.append(media_id)
                        print(f"   ✅ Image {idx} uploaded: {media_id}")
                    else:
                        print(f"   ⚠️ Image {idx} upload failed, continuing...")
            
            # Upload videos (chunked upload - THE FIX)
            if video_urls:
                print(f"🐦 Twitter: Uploading video using CHUNKED UPLOAD")
                video_id = await cls._upload_video_chunked(twitter, video_urls[0])
                if video_id:
                    media_ids.append(video_id)
                    print(f"   ✅ Video uploaded: {video_id}")
                else:
                    print(f"   ❌ Video upload failed")
                    return cls.format_error_response(
                        "Video upload failed. Check logs for details."
                    )
            
            # ✅ STEP 2: Create tweet using v2 API
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
            
            # ✅ Handle response
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
                print(f"❌ Twitter: 401 Unauthorized - {error_msg}")
                
                return cls.format_error_response(
                    f"Authentication failed: {error_msg}. "
                    "Please try reconnecting your Twitter account."
                )
            
            elif response.status_code == 403:
                error_data = response.json() if response.text else {}
                error_msg = cls._parse_error_message(error_data)
                print(f"❌ Twitter: 403 Forbidden - {error_msg}")
                
                if "Read and write" in error_msg or "permission" in error_msg.lower():
                    return cls.format_error_response(
                        "Twitter app lacks 'Read and Write' permissions. "
                        "Please check your Twitter Developer Portal settings."
                    )
                
                return cls.format_error_response(f"Forbidden: {error_msg}")
            
            elif response.status_code == 429:
                print(f"❌ Twitter: 429 Rate Limit Exceeded")
                return cls.format_error_response(
                    "Twitter API rate limit exceeded. Please wait a few minutes."
                )
            
            else:
                error_data = response.json() if response.text else {}
                error_msg = cls._parse_error_message(error_data)
                print(f"❌ Twitter: Error {response.status_code} - {error_msg}")
                
                return cls.format_error_response(
                    f"Tweet failed ({response.status_code}): {error_msg}"
                )
                
        except Exception as e:
            print(f"❌ Twitter post error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(f"Unexpected error: {str(e)}")
    
    @classmethod
    async def _upload_image(
        cls,
        twitter_session: OAuth1Session,
        image_url: str,
        index: int = 1
    ) -> Optional[str]:
        """
        Upload image using simple upload endpoint.
        
        Args:
            twitter_session: OAuth1Session instance
            image_url: URL of the image to upload
            index: Image number (for logging)
        
        Returns:
            media_id_string if successful, None otherwise
        """
        try:
            print(f"   📥 Downloading image {index}...")
            media_data = await cls.download_media(image_url, timeout=60)
            if not media_data:
                print(f"   ❌ Failed to download image")
                return None
            
            media_size_mb = len(media_data) / (1024 * 1024)
            print(f"   📦 Image size: {media_size_mb:.2f}MB")
            
            # Determine content type
            content_type = mimetypes.guess_type(image_url)[0] or "image/jpeg"
            
            # Upload using simple endpoint (works for images)
            files = {
                "media": (
                    f"image.{content_type.split('/')[-1]}", 
                    BytesIO(media_data), 
                    content_type
                )
            }
            
            response = twitter_session.post(
                f"{cls.UPLOAD_BASE}/media/upload.json",
                files=files,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("media_id_string")
            else:
                print(f"   ❌ Image upload failed: {response.status_code}")
                print(f"   ❌ Response: {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"   ❌ Image upload error: {e}")
            return None
    
    @classmethod
    async def _upload_video_chunked(
        cls,
        twitter_session: OAuth1Session,
        video_url: str
    ) -> Optional[str]:
        """
        ✅ MAIN FIX: Upload video using proper chunked upload process.
        
        This is the correct way to upload videos to Twitter:
        1. INIT - Initialize upload with file size and type
        2. APPEND - Upload file in chunks (max 5MB per chunk)
        3. FINALIZE - Complete the upload
        4. STATUS - Wait for processing (if needed)
        
        Args:
            twitter_session: OAuth1Session instance
            video_url: URL of the video to upload
        
        Returns:
            media_id_string if successful, None otherwise
        """
        try:
            # Download video
            print(f"   📥 Downloading video...")
            video_data = await cls.download_media(video_url, timeout=180)
            if not video_data:
                print(f"   ❌ Failed to download video")
                return None
            
            video_size = len(video_data)
            video_size_mb = video_size / (1024 * 1024)
            print(f"   📦 Video size: {video_size_mb:.2f}MB ({video_size} bytes)")
            
            # Validate size
            if video_size_mb > cls.MAX_VIDEO_SIZE_MB:
                print(f"   ❌ Video too large: {video_size_mb:.2f}MB (max {cls.MAX_VIDEO_SIZE_MB}MB)")
                return None
            
            # Determine media type
            media_type = mimetypes.guess_type(video_url)[0] or "video/mp4"
            print(f"   🎬 Media type: {media_type}")
            
            # ========================================================
            # STEP 1: INIT - Initialize chunked upload
            # ========================================================
            print(f"   📤 INIT: Initializing chunked upload...")
            
            init_data = {
                "command": "INIT",
                "total_bytes": str(video_size),
                "media_type": media_type,
                "media_category": "tweet_video"  # Required for videos
            }
            
            init_response = twitter_session.post(
                f"{cls.UPLOAD_BASE}/media/upload.json",
                data=init_data,
                timeout=30
            )
            
            if init_response.status_code != 200 and init_response.status_code != 201:
                print(f"   ❌ INIT failed: {init_response.status_code}")
                print(f"   ❌ Response: {init_response.text}")
                return None
            
            init_result = init_response.json()
            media_id = init_result.get("media_id_string")
            
            if not media_id:
                print(f"   ❌ No media_id received from INIT")
                return None
            
            print(f"   ✅ INIT successful. Media ID: {media_id}")
            
            # ========================================================
            # STEP 2: APPEND - Upload video in chunks
            # ========================================================
            print(f"   📤 APPEND: Uploading video in chunks...")
            
            segment_index = 0
            bytes_sent = 0
            
            while bytes_sent < video_size:
                # Get chunk
                chunk_start = bytes_sent
                chunk_end = min(bytes_sent + cls.CHUNK_SIZE, video_size)
                chunk = video_data[chunk_start:chunk_end]
                chunk_size = len(chunk)
                
                print(f"   📦 Uploading chunk {segment_index + 1} "
                      f"({bytes_sent}-{chunk_end}/{video_size} bytes)")
                
                # Upload chunk
                append_data = {
                    "command": "APPEND",
                    "media_id": media_id,
                    "segment_index": str(segment_index)
                }
                
                append_files = {
                    "media": BytesIO(chunk)
                }
                
                append_response = twitter_session.post(
                    f"{cls.UPLOAD_BASE}/media/upload.json",
                    data=append_data,
                    files=append_files,
                    timeout=120
                )
                
                # APPEND returns 204 No Content on success
                if append_response.status_code not in [200, 201, 204]:
                    print(f"   ❌ APPEND failed at segment {segment_index}: {append_response.status_code}")
                    print(f"   ❌ Response: {append_response.text}")
                    return None
                
                print(f"   ✅ Chunk {segment_index + 1} uploaded successfully")
                
                bytes_sent += chunk_size
                segment_index += 1
            
            print(f"   ✅ All {segment_index} chunks uploaded")
            
            # ========================================================
            # STEP 3: FINALIZE - Complete the upload
            # ========================================================
            print(f"   📤 FINALIZE: Completing upload...")
            
            finalize_data = {
                "command": "FINALIZE",
                "media_id": media_id
            }
            
            finalize_response = twitter_session.post(
                f"{cls.UPLOAD_BASE}/media/upload.json",
                data=finalize_data,
                timeout=60
            )
            
            if finalize_response.status_code != 200 and finalize_response.status_code != 201:
                print(f"   ❌ FINALIZE failed: {finalize_response.status_code}")
                print(f"   ❌ Response: {finalize_response.text}")
                return None
            
            finalize_result = finalize_response.json()
            print(f"   ✅ FINALIZE successful")
            
            # ========================================================
            # STEP 4: STATUS - Wait for processing (if needed)
            # ========================================================
            processing_info = finalize_result.get("processing_info")
            
            if processing_info:
                state = processing_info.get("state")
                print(f"   ⏳ Video processing: {state}")
                
                # Wait for processing to complete
                max_wait_time = 300  # 5 minutes
                start_time = time.time()
                check_after_secs = processing_info.get("check_after_secs", 5)
                
                while state in ["pending", "in_progress"]:
                    # Check if we've waited too long
                    if time.time() - start_time > max_wait_time:
                        print(f"   ❌ Video processing timeout after {max_wait_time}s")
                        return None
                    
                    # Wait before checking status
                    print(f"   ⏳ Waiting {check_after_secs}s before status check...")
                    await asyncio.sleep(check_after_secs)
                    
                    # Check status
                    status_data = {
                        "command": "STATUS",
                        "media_id": media_id
                    }
                    
                    status_response = twitter_session.get(
                        f"{cls.UPLOAD_BASE}/media/upload.json",
                        params=status_data,
                        timeout=30
                    )
                    
                    if status_response.status_code != 200:
                        print(f"   ❌ STATUS check failed: {status_response.status_code}")
                        return None
                    
                    status_result = status_response.json()
                    processing_info = status_result.get("processing_info", {})
                    state = processing_info.get("state")
                    check_after_secs = processing_info.get("check_after_secs", 5)
                    
                    print(f"   ⏳ Processing state: {state}")
                
                # Check final state
                if state == "succeeded":
                    print(f"   ✅ Video processing completed successfully")
                elif state == "failed":
                    error = processing_info.get("error", {})
                    error_msg = error.get("message", "Unknown error")
                    print(f"   ❌ Video processing failed: {error_msg}")
                    return None
            
            print(f"   🎉 Video upload complete! Media ID: {media_id}")
            return media_id
            
        except Exception as e:
            print(f"   ❌ Video upload error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @classmethod
    def _parse_error_message(cls, error_data: Dict) -> str:
        """Parse Twitter API error response"""
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
        
        # Simple error format
        if "error" in error_data:
            return error_data["error"]
        
        return str(error_data)
    
    @classmethod
    async def validate_token(cls, access_token: str) -> bool:
        """
        Validate Twitter OAuth tokens.
        
        Args:
            access_token: Format "oauth_token:oauth_token_secret"
        
        Returns:
            True if valid, False otherwise
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
            
            # Use v2 /users/me endpoint (lightweight)
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
    
   