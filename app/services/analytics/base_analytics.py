# app/services/platforms/base_platform.py
"""
Base platform service with shared utilities.
✅ Added: download_media() helper for async media downloads
"""

import httpx
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod


class BasePlatformService(ABC):
    """Abstract base class for all social media platform services"""
    
    # Platform metadata
    PLATFORM_NAME = "UNKNOWN"
    MAX_IMAGES = 0
    MAX_VIDEOS = 0
    MAX_VIDEO_SIZE_MB = 0
    MAX_VIDEO_DURATION_SECONDS = 0
    
    @classmethod
    @abstractmethod
    async def post(
        cls,
        access_token: str,
        content: str,
        image_urls: Optional[list] = None,
        video_urls: Optional[list] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Post content to the platform"""
        pass
    
    @classmethod
    @abstractmethod
    async def validate_token(cls, access_token: str) -> bool:
        """Validate platform access token"""
        pass
    
    @classmethod
    def validate_media_count(
        cls,
        image_urls: Optional[list] = None,
        video_urls: Optional[list] = None
    ) -> Optional[str]:
        """
        Validate media counts against platform limits.
        
        Returns:
            Error message if validation fails, None otherwise
        """
        images = image_urls or []
        videos = video_urls or []
        
        if len(images) > cls.MAX_IMAGES:
            return f"{cls.PLATFORM_NAME} allows max {cls.MAX_IMAGES} images, got {len(images)}"
        
        if len(videos) > cls.MAX_VIDEOS:
            return f"{cls.PLATFORM_NAME} allows max {cls.MAX_VIDEOS} video, got {len(videos)}"
        
        if images and videos:
            if cls.PLATFORM_NAME in ["TWITTER", "INSTAGRAM"]:
                return f"{cls.PLATFORM_NAME} doesn't support mixing images and videos"
        
        return None
    
    @classmethod
    def format_success_response(
        cls,
        platform_post_id: str,
        url: str
    ) -> Dict[str, Any]:
        """Format a successful post response"""
        return {
            "success": True,
            "platform": cls.PLATFORM_NAME,
            "platform_post_id": platform_post_id,
            "url": url
        }
    
    @classmethod
    def format_error_response(cls, error: str) -> Dict[str, Any]:
        """Format an error response"""
        return {
            "success": False,
            "platform": cls.PLATFORM_NAME,
            "error": error
        }
    
    @classmethod
    async def download_media(
        cls,
        media_url: str,
        timeout: int = 120
    ) -> Optional[bytes]:
        """
        Download media file from URL.
        
        Args:
            media_url: URL of the media file
            timeout: Request timeout in seconds
        
        Returns:
            Media file as bytes, or None if download fails
        """
        try:
            print(f"   📥 Downloading from: {media_url[:80]}...")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    media_url,
                    timeout=timeout,
                    follow_redirects=True
                )
                
                if response.status_code == 200:
                    data = response.content
                    size_mb = len(data) / (1024 * 1024)
                    print(f"   ✅ Downloaded {size_mb:.2f}MB")
                    return data
                else:
                    print(f"   ❌ Download failed: HTTP {response.status_code}")
                    return None
                    
        except httpx.TimeoutException:
            print(f"   ❌ Download timeout after {timeout}s")
            return None
        except Exception as e:
            print(f"   ❌ Download error: {e}")
            return None