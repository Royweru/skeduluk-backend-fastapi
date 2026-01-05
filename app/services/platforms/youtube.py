# app/services/platforms/youtube.py
"""
YouTube platform service for video uploads.
Requires YouTube Data API v3 to be enabled in Google Cloud Console.
âœ… FIXED: Proper multipart/related format for video uploads
"""

import httpx
import json
from typing import Dict, List, Any, Optional
from .base_platform import BasePlatformService


class YouTubeService(BasePlatformService):
    """YouTube platform service implementation"""
    
    PLATFORM_NAME = "YOUTUBE"
    MAX_IMAGES = 0
    MAX_VIDEOS = 1
    MAX_VIDEO_SIZE_MB = 128 * 1024  # 128GB
    MAX_VIDEO_DURATION_SECONDS = 3600
    
    API_BASE = "https://www.googleapis.com/youtube/v3"
    UPLOAD_BASE = "https://www.googleapis.com/upload/youtube/v3"
    
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
        Upload video to YouTube using proper multipart format.
        
        Args:
            access_token: Google OAuth access token
            content: Video title and description
            video_urls: List with one video URL
            **kwargs: Additional params like privacy_status, category_id, tags
        """
        print(f"🎬 YouTube: Starting video upload")
        
        # Validate video requirement
        if not video_urls or len(video_urls) == 0:
            return cls.format_error_response("YouTube requires a video")
        
        # Validate media counts
        error = cls.validate_media_count(image_urls, video_urls)
        if error:
            return cls.format_error_response(error)
        
        try:
            # Download video
            video_url = video_urls[0]
            print(f"🎬 YouTube: Downloading video from {video_url}")
            video_data = await cls.download_media(video_url, timeout=300)
            
            if not video_data:
                return cls.format_error_response("Failed to download video")
            
            video_size_mb = len(video_data) / (1024 * 1024)
            print(f"🎬 YouTube: Video size: {video_size_mb:.2f} MB")
            
            # Choose upload method based on size
            if video_size_mb > 5:
                print(f"🎬 YouTube: Using resumable upload (video > 5MB)")
                return await cls._resumable_upload(
                    access_token, content, video_data, **kwargs
                )
            else:
                print(f"🎬 YouTube: Using simple multipart upload (video < 5MB)")
                return await cls._simple_multipart_upload(
                    access_token, content, video_data, **kwargs
                )
                
        except Exception as e:
            print(f"❌ YouTube upload error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
    @classmethod
    async def _simple_multipart_upload(
        cls,
        access_token: str,
        content: str,
        video_data: bytes,
        **kwargs
    ) -> Dict[str, Any]:
        """
        âœ… FIXED: Simple multipart upload with proper multipart/related format
        """
        # Extract parameters
        title = content[:100] if len(content) <= 100 else content[:97] + "..."
        description = content
        privacy_status = kwargs.get("privacy_status", "public")
        category_id = kwargs.get("category_id", "22")
        tags = kwargs.get("tags", [])
        
        # Prepare metadata
        metadata = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }
        
        if tags:
            metadata["snippet"]["tags"] = tags
        
        # âœ… FIX: Create proper multipart/related body
        boundary = "===============7330845974216740156=="
        
        # Part 1: JSON metadata with proper Content-Type
        metadata_part = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json; charset=UTF-8\r\n"
            f"\r\n"
            f"{json.dumps(metadata)}\r\n"
        )
        
        # Part 2: Video binary data with proper Content-Type
        video_part_header = (
            f"--{boundary}\r\n"
            f"Content-Type: video/mp4\r\n"
            f"\r\n"
        )
        
        # Part 3: Closing boundary
        closing_boundary = f"\r\n--{boundary}--"
        
        # Combine all parts
        body = (
            metadata_part.encode('utf-8') +
            video_part_header.encode('utf-8') +
            video_data +
            closing_boundary.encode('utf-8')
        )
        
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                print(f"🎬 YouTube: Uploading video ({video_size_mb:.2f}MB)...")
                
                response = await client.post(
                    f"{cls.UPLOAD_BASE}/videos",
                    params={
                        "part": "snippet,status",
                        "uploadType": "multipart"
                    },
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": f"multipart/related; boundary={boundary}"
                    },
                    content=body
                )
                
                return cls._handle_upload_response(response)
                
        except Exception as e:
            print(f"❌ YouTube multipart upload error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
    @classmethod
    async def _resumable_upload(
        cls,
        access_token: str,
        content: str,
        video_data: bytes,
        **kwargs
    ) -> Dict[str, Any]:
        """
        âœ… Resumable upload for larger videos (more reliable)
        """
        # Extract parameters
        title = content[:100] if len(content) <= 100 else content[:97] + "..."
        description = content
        privacy_status = kwargs.get("privacy_status", "public")
        category_id = kwargs.get("category_id", "22")
        tags = kwargs.get("tags", [])
        
        # Prepare metadata
        metadata = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }
        
        if tags:
            metadata["snippet"]["tags"] = tags
        
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                # Step 1: Initialize resumable upload
                print(f"🎬 YouTube: Initializing resumable upload...")
                
                init_response = await client.post(
                    f"{cls.UPLOAD_BASE}/videos",
                    params={
                        "part": "snippet,status",
                        "uploadType": "resumable"
                    },
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json; charset=UTF-8",
                        "X-Upload-Content-Type": "video/mp4",
                        "X-Upload-Content-Length": str(len(video_data))
                    },
                    json=metadata
                )
                
                if init_response.status_code not in [200, 201]:
                    error_text = init_response.text
                    print(f"❌ YouTube init failed: {init_response.status_code}")
                    print(f"❌ Error: {error_text}")
                    return cls._handle_upload_response(init_response)
                
                # Get upload URL from Location header
                upload_url = init_response.headers.get("Location")
                if not upload_url:
                    return cls.format_error_response("No upload URL returned")
                
                print(f"🎬 YouTube: Got upload URL, uploading video data...")
                
                # Step 2: Upload video data
                upload_response = await client.put(
                    upload_url,
                    headers={
                        "Content-Type": "video/mp4"
                    },
                    content=video_data
                )
                
                return cls._handle_upload_response(upload_response)
                
        except Exception as e:
            print(f"❌ YouTube resumable upload error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
    @classmethod
    def _handle_upload_response(cls, response: httpx.Response) -> Dict[str, Any]:
        """Handle YouTube API response"""
        print(f"🎬 YouTube: Response status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            video_id = data.get("id")
            
            print(f"✅ YouTube: Video uploaded successfully - ID: {video_id}")
            
            return cls.format_success_response(
                video_id,
                f"https://www.youtube.com/watch?v={video_id}",
                video_id=video_id
            )
        else:
            error_text = response.text
            print(f"❌ YouTube upload failed: {response.status_code}")
            print(f"❌ Error response: {error_text}")
            
            # Parse error and provide helpful messages
            try:
                error_json = response.json()
                error_message = error_json.get("error", {}).get("message", error_text)
            except:
                error_message = error_text
            
            # Check for specific errors
            if "quotaExceeded" in error_text:
                return cls.format_error_response(
                    "YouTube API quota exceeded. Try again tomorrow."
                )
            elif "Daily Limit Exceeded" in error_text:
                return cls.format_error_response(
                    "YouTube daily upload limit exceeded"
                )
            elif "has not been used" in error_text or "is disabled" in error_text:
                return cls.format_error_response(
                    "YouTube Data API v3 is not enabled. Enable it in Google Cloud Console: "
                    "https://console.cloud.google.com/apis/library/youtube.googleapis.com"
                )
            elif "Media type" in error_text and "not supported" in error_text:
                return cls.format_error_response(
                    f"Upload format error: {error_message}. This should not happen with the fixed code. "
                    "Please ensure you're using the latest youtube.py file."
                )
            else:
                return cls.format_error_response(f"Upload failed: {error_message}")
    
    @classmethod
    async def validate_token(cls, access_token: str) -> bool:
        """Validate YouTube/Google access token"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{cls.API_BASE}/channels",
                    params={"part": "snippet", "mine": "true"},
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                return response.status_code == 200
        except:
            return False
    
    @classmethod
    async def get_channel_info(cls, access_token: str) -> Optional[Dict[str, Any]]:
        """Get YouTube channel information"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{cls.API_BASE}/channels",
                    params={"part": "snippet,statistics", "mine": "true"},
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("items"):
                        channel = data["items"][0]
                        return {
                            "id": channel["id"],
                            "title": channel["snippet"]["title"],
                            "subscriber_count": channel["statistics"].get("subscriberCount", 0),
                            "video_count": channel["statistics"].get("videoCount", 0),
                            "thumbnail": channel["snippet"]["thumbnails"]["default"]["url"]
                        }
            return None
        except:
            return None# app/services/platforms/youtube.py
"""
YouTube platform service for video uploads.
Requires YouTube Data API v3 to be enabled in Google Cloud Console.
âœ… FIXED: Proper multipart/related format for video uploads
"""

import httpx
import json
from typing import Dict, List, Any, Optional
from .base_platform import BasePlatformService


class YouTubeService(BasePlatformService):
    """YouTube platform service implementation"""
    
    PLATFORM_NAME = "YOUTUBE"
    MAX_IMAGES = 0
    MAX_VIDEOS = 1
    MAX_VIDEO_SIZE_MB = 128 * 1024  # 128GB
    MAX_VIDEO_DURATION_SECONDS = 3600
    
    API_BASE = "https://www.googleapis.com/youtube/v3"
    UPLOAD_BASE = "https://www.googleapis.com/upload/youtube/v3"
    
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
        Upload video to YouTube using proper multipart format.
        
        Args:
            access_token: Google OAuth access token
            content: Video title and description
            video_urls: List with one video URL
            **kwargs: Additional params like privacy_status, category_id, tags
        """
        print(f"🎬 YouTube: Starting video upload")
        
        # Validate video requirement
        if not video_urls or len(video_urls) == 0:
            return cls.format_error_response("YouTube requires a video")
        
        # Validate media counts
        error = cls.validate_media_count(image_urls, video_urls)
        if error:
            return cls.format_error_response(error)
        
        try:
            # Download video
            video_url = video_urls[0]
            print(f"🎬 YouTube: Downloading video from {video_url}")
            video_data = await cls.download_media(video_url, timeout=300)
            
            if not video_data:
                return cls.format_error_response("Failed to download video")
            
            video_size_mb = len(video_data) / (1024 * 1024)
            print(f"🎬 YouTube: Video size: {video_size_mb:.2f} MB")
            
            # Choose upload method based on size
            if video_size_mb > 5:
                print(f"🎬 YouTube: Using resumable upload (video > 5MB)")
                return await cls._resumable_upload(
                    access_token, content, video_data, **kwargs
                )
            else:
                print(f"🎬 YouTube: Using simple multipart upload (video < 5MB)")
                return await cls._simple_multipart_upload(
                    access_token, content, video_data, **kwargs
                )
                
        except Exception as e:
            print(f"❌ YouTube upload error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
    @classmethod
    async def _simple_multipart_upload(
        cls,
        access_token: str,
        content: str,
        video_data: bytes,
        **kwargs
    ) -> Dict[str, Any]:
        """
        âœ… FIXED: Simple multipart upload with proper multipart/related format
        """
        # Extract parameters
        title = content[:100] if len(content) <= 100 else content[:97] + "..."
        description = content
        privacy_status = kwargs.get("privacy_status", "public")
        category_id = kwargs.get("category_id", "22")
        tags = kwargs.get("tags", [])
        
        # Prepare metadata
        metadata = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }
        
        if tags:
            metadata["snippet"]["tags"] = tags
        
        # âœ… FIX: Create proper multipart/related body
        boundary = "===============7330845974216740156=="
        
        # Part 1: JSON metadata with proper Content-Type
        metadata_part = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json; charset=UTF-8\r\n"
            f"\r\n"
            f"{json.dumps(metadata)}\r\n"
        )
        
        # Part 2: Video binary data with proper Content-Type
        video_part_header = (
            f"--{boundary}\r\n"
            f"Content-Type: video/mp4\r\n"
            f"\r\n"
        )
        
        # Part 3: Closing boundary
        closing_boundary = f"\r\n--{boundary}--"
        
        # Combine all parts
        body = (
            metadata_part.encode('utf-8') +
            video_part_header.encode('utf-8') +
            video_data +
            closing_boundary.encode('utf-8')
        )
        
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                print(f"🎬 YouTube: Uploading video ({video_size_mb:.2f}MB)...")
                
                response = await client.post(
                    f"{cls.UPLOAD_BASE}/videos",
                    params={
                        "part": "snippet,status",
                        "uploadType": "multipart"
                    },
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": f"multipart/related; boundary={boundary}"
                    },
                    content=body
                )
                
                return cls._handle_upload_response(response)
                
        except Exception as e:
            print(f"❌ YouTube multipart upload error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
    @classmethod
    async def _resumable_upload(
        cls,
        access_token: str,
        content: str,
        video_data: bytes,
        **kwargs
    ) -> Dict[str, Any]:
        """
        âœ… Resumable upload for larger videos (more reliable)
        """
        # Extract parameters
        title = content[:100] if len(content) <= 100 else content[:97] + "..."
        description = content
        privacy_status = kwargs.get("privacy_status", "public")
        category_id = kwargs.get("category_id", "22")
        tags = kwargs.get("tags", [])
        
        # Prepare metadata
        metadata = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }
        
        if tags:
            metadata["snippet"]["tags"] = tags
        
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                # Step 1: Initialize resumable upload
                print(f"🎬 YouTube: Initializing resumable upload...")
                
                init_response = await client.post(
                    f"{cls.UPLOAD_BASE}/videos",
                    params={
                        "part": "snippet,status",
                        "uploadType": "resumable"
                    },
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json; charset=UTF-8",
                        "X-Upload-Content-Type": "video/mp4",
                        "X-Upload-Content-Length": str(len(video_data))
                    },
                    json=metadata
                )
                
                if init_response.status_code not in [200, 201]:
                    error_text = init_response.text
                    print(f"❌ YouTube init failed: {init_response.status_code}")
                    print(f"❌ Error: {error_text}")
                    return cls._handle_upload_response(init_response)
                
                # Get upload URL from Location header
                upload_url = init_response.headers.get("Location")
                if not upload_url:
                    return cls.format_error_response("No upload URL returned")
                
                print(f"🎬 YouTube: Got upload URL, uploading video data...")
                
                # Step 2: Upload video data
                upload_response = await client.put(
                    upload_url,
                    headers={
                        "Content-Type": "video/mp4"
                    },
                    content=video_data
                )
                
                return cls._handle_upload_response(upload_response)
                
        except Exception as e:
            print(f"❌ YouTube resumable upload error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
    @classmethod
    def _handle_upload_response(cls, response: httpx.Response) -> Dict[str, Any]:
        """Handle YouTube API response"""
        print(f"🎬 YouTube: Response status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            video_id = data.get("id")
            
            print(f"✅ YouTube: Video uploaded successfully - ID: {video_id}")
            
            return cls.format_success_response(
                video_id,
                f"https://www.youtube.com/watch?v={video_id}",
                video_id=video_id
            )
        else:
            error_text = response.text
            print(f"❌ YouTube upload failed: {response.status_code}")
            print(f"❌ Error response: {error_text}")
            
            # Parse error and provide helpful messages
            try:
                error_json = response.json()
                error_message = error_json.get("error", {}).get("message", error_text)
            except:
                error_message = error_text
            
            # Check for specific errors
            if "quotaExceeded" in error_text:
                return cls.format_error_response(
                    "YouTube API quota exceeded. Try again tomorrow."
                )
            elif "Daily Limit Exceeded" in error_text:
                return cls.format_error_response(
                    "YouTube daily upload limit exceeded"
                )
            elif "has not been used" in error_text or "is disabled" in error_text:
                return cls.format_error_response(
                    "YouTube Data API v3 is not enabled. Enable it in Google Cloud Console: "
                    "https://console.cloud.google.com/apis/library/youtube.googleapis.com"
                )
            elif "Media type" in error_text and "not supported" in error_text:
                return cls.format_error_response(
                    f"Upload format error: {error_message}. This should not happen with the fixed code. "
                    "Please ensure you're using the latest youtube.py file."
                )
            else:
                return cls.format_error_response(f"Upload failed: {error_message}")
    
    @classmethod
    async def validate_token(cls, access_token: str) -> bool:
        """Validate YouTube/Google access token"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{cls.API_BASE}/channels",
                    params={"part": "snippet", "mine": "true"},
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                return response.status_code == 200
        except:
            return False
    
    @classmethod
    async def get_channel_info(cls, access_token: str) -> Optional[Dict[str, Any]]:
        """Get YouTube channel information"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{cls.API_BASE}/channels",
                    params={"part": "snippet,statistics", "mine": "true"},
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("items"):
                        channel = data["items"][0]
                        return {
                            "id": channel["id"],
                            "title": channel["snippet"]["title"],
                            "subscriber_count": channel["statistics"].get("subscriberCount", 0),
                            "video_count": channel["statistics"].get("videoCount", 0),
                            "thumbnail": channel["snippet"]["thumbnails"]["default"]["url"]
                        }
            return None
        except:
            return None