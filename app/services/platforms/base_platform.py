# app/services/platforms/base_platform.py
"""
Abstract base class for all social media platform services.
Provides common interface and utilities for platform-specific implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import httpx
from datetime import datetime


class BasePlatformService(ABC):
    """
    Abstract base class for social media platforms.
    All platform services must inherit from this class.
    """
    
    PLATFORM_NAME: str = "UNKNOWN"
    MAX_IMAGES: int = 0
    MAX_VIDEOS: int = 0
    MAX_VIDEO_SIZE_MB: int = 0
    MAX_VIDEO_DURATION_SECONDS: int = 0
    
    @abstractmethod
    async def post(
        self,
        access_token: str,
        content: str,
        image_urls: Optional[List[str]] = None,
        video_urls: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Post content to the platform.
        
        Args:
            access_token: Platform access token
            content: Text content to post
            image_urls: List of image URLs to attach
            video_urls: List of video URLs to attach
            **kwargs: Platform-specific additional parameters
            
        Returns:
            Dict with keys: success, platform_post_id, url, error (if failed)
        """
        pass
    
    @abstractmethod
    async def validate_token(self, access_token: str) -> bool:
        """Validate if the access token is still valid"""
        pass
    
    @classmethod
    async def download_media(cls, url: str, timeout: int = 60) -> Optional[bytes]:
        """
        Download media file from URL.
        
        Args:
            url: Media file URL
            timeout: Request timeout in seconds
            
        Returns:
            File content as bytes or None if failed
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.content
                print(f"❌ Failed to download media: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error downloading media: {e}")
            return None
    
    @classmethod
    def format_error_response(cls, error: str) -> Dict[str, Any]:
        """Format error response"""
        return {
            "success": False,
            "error": f"{cls.PLATFORM_NAME} error: {error}",
            "platform": cls.PLATFORM_NAME
        }
    
    @classmethod
    def format_success_response(
        cls,
        platform_post_id: str,
        url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Format success response"""
        return {
            "success": True,
            "platform_post_id": platform_post_id,
            "url": url,
            "platform": cls.PLATFORM_NAME,
            **kwargs
        }
    
    @classmethod
    def validate_media_count(
        cls,
        image_urls: Optional[List[str]],
        video_urls: Optional[List[str]]
    ) -> Optional[str]:
        """
        Validate media counts against platform limits.
        Returns error message if validation fails, None if passes.
        """
        image_count = len(image_urls) if image_urls else 0
        video_count = len(video_urls) if video_urls else 0
        
        if image_count > cls.MAX_IMAGES:
            return f"{cls.PLATFORM_NAME} allows max {cls.MAX_IMAGES} images, got {image_count}"
        
        if video_count > cls.MAX_VIDEOS:
            return f"{cls.PLATFORM_NAME} allows max {cls.MAX_VIDEOS} videos, got {video_count}"
        
        return None