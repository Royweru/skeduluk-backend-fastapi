# app/services/platforms/youtube.py
"""
YouTube platform service for video uploads.
Requires YouTube Data API v3 to be enabled in Google Cloud Console.
"""

import httpx
from typing import Dict, List, Any, Optional
from .base_platform import BasePlatformService


class YouTubeService(BasePlatformService):
    """YouTube platform service implementation"""
    
    PLATFORM_NAME = "YOUTUBE"
    MAX_IMAGES = 0  # YouTube doesn't support images in posts
    MAX_VIDEOS = 1
    MAX_VIDEO_SIZE_MB = 128 * 1024  # 128GB
    MAX_VIDEO_DURATION_SECONDS = 3600  # 1 hour for unverified, 12 hours for verified
    
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
        Upload video to YouTube.
        
        Args:
            access_token: Google OAuth access token
            content: Video title and description
            video_urls: List with one video URL
            **kwargs: Additional params like privacy_status, category_id, tags
        """
        print(f"🎬 YouTube: Starting video upload")
        
        # YouTube requires video
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
            video_data = await cls.download_media(video_url, timeout=300)  # 5 min timeout
            
            if not video_data:
                return cls.format_error_response("Failed to download video")
            
            video_size_mb = len(video_data) / (1024 * 1024)
            print(f"🎬 YouTube: Video size: {video_size_mb:.2f} MB")
            
            # Extract title and description
            title = content[:100] if len(content) <= 100 else content[:97] + "..."
            description = content
            
            # Get parameters
            privacy_status = kwargs.get("privacy_status", "public")  # public, unlisted, private
            category_id = kwargs.get("category_id", "22")  # 22 = People & Blogs
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
            
            # Upload video
            async with httpx.AsyncClient(timeout=600.0) as client:  # 10 min timeout
                print(f"🎬 YouTube: Uploading video ({video_size_mb:.2f} MB)...")
                
                # Use multipart upload
                files = {
                    "video": ("video.mp4", video_data, "video/mp4")
                }
                
                response = await client.post(
                    f"{cls.UPLOAD_BASE}/videos",
                    params={
                        "part": "snippet,status",
                        "uploadType": "multipart"
                    },
                    headers={
                        "Authorization": f"Bearer {access_token}",
                    },
                    data={
                        "resource": str(metadata)  # Metadata as JSON string
                    },
                    files=files
                )
                
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
                    print(f"❌ Error: {error_text}")
                    
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
                    else:
                        return cls.format_error_response(f"Upload failed: {error_text}")
                
        except Exception as e:
            print(f"❌ YouTube upload error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
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