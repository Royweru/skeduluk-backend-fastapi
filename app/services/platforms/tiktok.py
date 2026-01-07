# app/services/platforms/tiktok.py
"""
TikTok platform service for video uploads.
Uses TikTok Content Posting API v2 with OAuth 2.0.
"""

import httpx
import asyncio
from typing import Dict, List, Any, Optional
from .base_platform import BasePlatformService


class TikTokService(BasePlatformService):
    """TikTok platform service implementation"""
    
    PLATFORM_NAME = "TIKTOK"
    MAX_IMAGES = 0  # TikTok is video-only via API
    MAX_VIDEOS = 1
    MAX_VIDEO_SIZE_MB = 4096  # 4GB
    MAX_VIDEO_DURATION_SECONDS = 600  # 10 minutes (can be up to 60 min for some accounts)
    
    # TikTok API endpoints
    API_BASE = "https://open.tiktokapis.com"
    OAUTH_BASE = "https://www.tiktok.com/v2/auth"
    
    # Rate limits
    MAX_STATUS_CHECKS = 60  # Check status up to 60 times
    STATUS_CHECK_INTERVAL = 5  # Check every 5 seconds
    
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
        Post video to TikTok using Content Posting API.
        
        Args:
            access_token: TikTok OAuth 2.0 access token
            content: Video title/caption
            video_urls: List with one video URL
            **kwargs: Additional params like privacy_level, disable_duet, etc.
        
        TikTok Posting Process:
        1. Initialize upload (get upload URL and publish_id)
        2. Upload video binary data to upload URL
        3. Poll status endpoint until processing complete
        """
        print(f"🎵 TikTok: Starting video upload")
        
        # Validate video requirement
        if not video_urls or len(video_urls) == 0:
            return cls.format_error_response("TikTok requires a video")
        
        # Validate media counts
        error = cls.validate_media_count(image_urls, video_urls)
        if error:
            return cls.format_error_response(error)
        
        try:
            # Download video
            video_url = video_urls[0]
            print(f"🎵 TikTok: Downloading video from {video_url}")
            video_data = await cls.download_media(video_url, timeout=300)
            
            if not video_data:
                return cls.format_error_response("Failed to download video")
            
            video_size = len(video_data)
            video_size_mb = video_size / (1024 * 1024)
            print(f"🎵 TikTok: Video size: {video_size_mb:.2f} MB")
            
            # Check size limit
            if video_size_mb > cls.MAX_VIDEO_SIZE_MB:
                return cls.format_error_response(
                    f"Video too large: {video_size_mb:.2f}MB (max: {cls.MAX_VIDEO_SIZE_MB}MB)"
                )
            
            # ✅ STEP 1: Initialize video upload
            publish_id, upload_url = await cls._initialize_video_upload(
                access_token, content, video_size, **kwargs
            )
            
            if not publish_id or not upload_url:
                return cls.format_error_response("Failed to initialize video upload")
            
            # ✅ STEP 2: Upload video data
            upload_success = await cls._upload_video_data(upload_url, video_data)
            
            if not upload_success:
                return cls.format_error_response("Failed to upload video data")
            
            # ✅ STEP 3: Wait for processing and check status
            result = await cls._wait_for_processing(access_token, publish_id)
            
            if result["success"]:
                print(f"✅ TikTok: Video posted successfully!")
                return result
            else:
                return result
            
        except Exception as e:
            print(f"❌ TikTok upload error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
    @classmethod
    async def _initialize_video_upload(
        cls,
        access_token: str,
        content: str,
        video_size: int,
        **kwargs
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Initialize TikTok video upload (Step 1).
        
        Returns:
            Tuple of (publish_id, upload_url) or (None, None) on failure
        """
        print(f"🎵 TikTok: Initializing video upload...")
        
        # Extract parameters
        privacy_level = kwargs.get("privacy_level", "SELF_ONLY")  # SELF_ONLY, MUTUAL_FOLLOW_FRIENDS, FOLLOWER_OF_CREATOR, PUBLIC_TO_EVERYONE
        disable_duet = kwargs.get("disable_duet", False)
        disable_comment = kwargs.get("disable_comment", False)
        disable_stitch = kwargs.get("disable_stitch", False)
        
        # Build request body
        request_body = {
            "post_info": {
                "title": content[:150],  # Max 150 chars for title
                "privacy_level": privacy_level,
                "disable_duet": disable_duet,
                "disable_comment": disable_comment,
                "disable_stitch": disable_stitch
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,  # Single chunk upload
                "total_chunk_count": 1
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{cls.API_BASE}/v2/post/publish/video/init/",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json; charset=UTF-8"
                    },
                    json=request_body
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check for error in response
                    if data.get("error", {}).get("code") != "ok":
                        error_msg = data.get("error", {}).get("message", "Unknown error")
                        print(f"❌ TikTok init failed: {error_msg}")
                        return None, None
                    
                    publish_id = data.get("data", {}).get("publish_id")
                    upload_url = data.get("data", {}).get("upload_url")
                    
                    print(f"✅ TikTok: Initialized - publish_id: {publish_id}")
                    return publish_id, upload_url
                else:
                    print(f"❌ TikTok init failed: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None, None
                    
        except Exception as e:
            print(f"❌ TikTok init error: {e}")
            return None, None
    
    @classmethod
    async def _upload_video_data(
        cls,
        upload_url: str,
        video_data: bytes
    ) -> bool:
        """
        Upload video binary data to TikTok (Step 2).
        
        Returns:
            True if successful, False otherwise
        """
        print(f"🎵 TikTok: Uploading video data...")
        
        video_size = len(video_data)
        
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.put(
                    upload_url,
                    headers={
                        "Content-Range": f"bytes 0-{video_size-1}/{video_size}",
                        "Content-Length": str(video_size),
                        "Content-Type": "video/mp4"
                    },
                    content=video_data
                )
                
                if response.status_code in [200, 201, 204]:
                    print(f"✅ TikTok: Video data uploaded successfully")
                    return True
                else:
                    print(f"❌ TikTok upload failed: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return False
                    
        except Exception as e:
            print(f"❌ TikTok upload error: {e}")
            return False
    
    @classmethod
    async def _wait_for_processing(
        cls,
        access_token: str,
        publish_id: str
    ) -> Dict[str, Any]:
        """
        Wait for TikTok to process the video (Step 3).
        
        Polls the status endpoint until video is published or fails.
        
        Returns:
            Success/error dict
        """
        print(f"🎵 TikTok: Waiting for video processing...")
        print(f"   (This can take 30 seconds to 5 minutes)")
        
        check_count = 0
        
        while check_count < cls.MAX_STATUS_CHECKS:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{cls.API_BASE}/v2/post/publish/status/fetch/",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json; charset=UTF-8"
                        },
                        json={"publish_id": publish_id}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Check for error in response
                        if data.get("error", {}).get("code") != "ok":
                            error_msg = data.get("error", {}).get("message", "Unknown error")
                            return cls.format_error_response(f"Status check failed: {error_msg}")
                        
                        status = data.get("data", {}).get("status")
                        
                        print(f"   📊 Status: {status} (check {check_count + 1}/{cls.MAX_STATUS_CHECKS})")
                        
                        # Check status
                        if status == "PUBLISH_COMPLETE":
                            # Get the post IDs
                            post_ids = data.get("data", {}).get("publicaly_available_post_id", [])
                            
                            if post_ids:
                                post_id = post_ids[0]
                                print(f"✅ TikTok: Video published successfully!")
                                print(f"   Post ID: {post_id}")
                                
                                # TikTok post URLs format: https://www.tiktok.com/@username/video/{post_id}
                                # Since we don't have username here, provide a generic URL
                                return cls.format_success_response(
                                    post_id,
                                    f"https://www.tiktok.com/video/{post_id}",
                                    post_id=post_id
                                )
                            else:
                                return cls.format_error_response("Video published but no post ID returned")
                        
                        elif status == "FAILED":
                            fail_reason = data.get("data", {}).get("fail_reason", "Unknown reason")
                            print(f"❌ TikTok: Video processing failed - {fail_reason}")
                            return cls.format_error_response(f"Video processing failed: {fail_reason}")
                        
                        elif status in ["PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD", "SEND_TO_USER_INBOX", "PUBLISH_QUEUED"]:
                            # Still processing, wait and check again
                            await asyncio.sleep(cls.STATUS_CHECK_INTERVAL)
                            check_count += 1
                            continue
                        
                        else:
                            # Unknown status
                            print(f"⚠️ TikTok: Unknown status - {status}")
                            await asyncio.sleep(cls.STATUS_CHECK_INTERVAL)
                            check_count += 1
                            continue
                    else:
                        print(f"❌ TikTok status check failed: {response.status_code}")
                        return cls.format_error_response(f"Status check failed: {response.status_code}")
                        
            except Exception as e:
                print(f"❌ TikTok status check error: {e}")
                return cls.format_error_response(f"Status check error: {str(e)}")
        
        # Timeout
        print(f"⏰ TikTok: Processing timeout after {cls.MAX_STATUS_CHECKS * cls.STATUS_CHECK_INTERVAL} seconds")
        return cls.format_error_response(
            "Video processing timeout. Video may still be processing on TikTok."
        )
    
    @classmethod
    async def validate_token(cls, access_token: str) -> bool:
        """Validate TikTok access token"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{cls.API_BASE}/v2/user/info/",
                    params={"fields": "open_id,display_name"},
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("error", {}).get("code") == "ok"
                
                return False
        except:
            return False
    
    @classmethod
    async def get_user_info(cls, access_token: str) -> Optional[Dict[str, Any]]:
        """Get TikTok user information"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{cls.API_BASE}/v2/user/info/",
                    params={"fields": "open_id,union_id,avatar_url,display_name"},
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("error", {}).get("code") == "ok":
                        user = data.get("data", {}).get("user", {})
                        return {
                            "open_id": user.get("open_id"),
                            "union_id": user.get("union_id"),
                            "display_name": user.get("display_name"),
                            "avatar_url": user.get("avatar_url")
                        }
            
            return None
        except:
            return None