# app/services/social_service.py
"""
Main social media service orchestrator.
 FIXED: Proper handling of Twitter OAuth 1.0a tokens
"""

from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ..models import SocialConnection
from .platforms import (
    TwitterService,
    FacebookService,
    InstagramService,
    LinkedInService,
    YouTubeService
)
from .oauth_service import OAuthService


class SocialService:
    """
    Main orchestrator for social media posting.
    Routes requests to platform-specific services.
    """
    
    # Platform service mapping
    PLATFORM_SERVICES = {
        "TWITTER": TwitterService,
        "FACEBOOK": FacebookService,
        "INSTAGRAM": InstagramService,
        "LINKEDIN": LinkedInService,
        "YOUTUBE": YouTubeService
    }
    
    #  NEW: Platforms that use OAuth 1.0a (no token refresh)
    OAUTH_1_0A_PLATFORMS = {"TWITTER"}
    
    @classmethod
    async def ensure_valid_token(
        cls,
        connection: SocialConnection,
        db: AsyncSession
    ) -> str:
        """
        Ensure token is valid, refresh if needed.
        
        ✅ FIXED: Aggressively skips refresh for Twitter/X (OAuth 1.0a)
        """
        # normalize: ensure string, uppercase, and remove ALL whitespace
        platform = str(connection.platform).upper().strip()
        
        # 🛑 HARD STOP: Explicitly check for Twitter to prevent ANY refresh attempt
        if "TWITTER" in platform or platform == "X":
            print(f" {platform}: OAuth 1.0a detected - Skipping token refresh.")
            return connection.access_token
            
        # Check standard OAuth 1.0a list
        if platform in cls.OAUTH_1_0A_PLATFORMS:
            print(f" {platform}: Using OAuth 1.0a token (no refresh needed)")
            return connection.access_token
        
        # Check if token is expired (for OAuth 2.0 platforms only)
        if connection.token_expires_at and connection.token_expires_at < datetime.utcnow():
            print(f" Token expired for {platform}, refreshing...")
            
            try:
                result = await OAuthService.refresh_access_token(connection, db)
                if not result:
                    # If refresh fails, try to return existing token as hail mary
                    print(f"] Refresh failed for {platform}, using existing token as fallback")
                    return connection.access_token
                
                return result["access_token"]
            except Exception as e:
                print(f"Token refresh failed for {platform}: {e}")
                # Don't crash the whole process, return the old token
                return connection.access_token
        
        return connection.access_token
    
    @classmethod
    async def publish_to_platform(
        cls,
        connection: SocialConnection,
        content: str,
        image_urls: Optional[List[str]] = None,
        video_urls: Optional[List[str]] = None,
        db: Optional[AsyncSession] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Publish content to a specific social platform.
        
        Args:
            connection: SocialConnection object
            content: Post content
            image_urls: List of image URLs
            video_urls: List of video URLs
            db: Database session (for token refresh)
            **kwargs: Platform-specific parameters
            
        Returns:
            Dict with keys: success, platform_post_id, url, error (if failed)
        """
        platform = connection.platform.upper()
        
        print(f"\n{'='*60}")
        print(f"🚀 Publishing to {platform}")
        print(f"{'='*60}")
        
        # Get platform service
        service_class = cls.PLATFORM_SERVICES.get(platform)
        if not service_class:
            return {
                "success": False,
                "error": f"Unsupported platform: {platform}",
                "platform": platform
            }
        
        try:
            # Ensure valid token
            if db:
                access_token = await cls.ensure_valid_token(connection, db)
            else:
                access_token = connection.access_token
            
            # Pass connection for platforms that need it (Facebook)
            if platform == "FACEBOOK":
                kwargs["connection"] = connection
            
            # Call platform-specific service
            result = await service_class.post(
                access_token=access_token,
                content=content,
                image_urls=image_urls,
                video_urls=video_urls,
                **kwargs
            )
            
            # Add platform to result
            result["platform"] = platform
            
            if result["success"]:
                print(f" {platform}: Posted successfully!")
                print(f"   URL: {result.get('url', 'N/A')}")
            else:
                print(f" {platform}: Failed - {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            print(f" {platform}: Exception - {error_msg}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": error_msg,
                "platform": platform
            }
    
    @classmethod
    async def publish_to_multiple_platforms(
        cls,
        connections: List[SocialConnection],
        content: str,
        image_urls: Optional[List[str]] = None,
        video_urls: Optional[List[str]] = None,
        db: Optional[AsyncSession] = None,
        platform_specific_content: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Publish to multiple platforms concurrently.
        
        Args:
            connections: List of social connections
            content: Default content for all platforms
            image_urls: Image URLs
            video_urls: Video URLs
            db: Database session
            platform_specific_content: Dict of platform -> custom content
            **kwargs: Additional parameters
            
        Returns:
            Summary dict with results for each platform
        """
        import asyncio
        
        print(f"\n{'='*60}")
        print(f"🚀 Multi-Platform Publishing")
        print(f"📝 Content: {content[:50]}...")
        print(f"🖼️ Images: {len(image_urls) if image_urls else 0}")
        print(f"🎬 Videos: {len(video_urls) if video_urls else 0}")
        print(f"{'='*60}\n")
        
        tasks = []
        for connection in connections:
            # Use platform-specific content if available
            platform_content = content
            if platform_specific_content and connection.platform.lower() in platform_specific_content:
                platform_content = platform_specific_content[connection.platform.lower()]
            
            # Create task
            task = cls.publish_to_platform(
                connection=connection,
                content=platform_content,
                image_urls=image_urls,
                video_urls=video_urls,
                db=db,
                **kwargs
            )
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful = []
        failed = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Task raised exception
                platform = connections[i].platform
                failed.append({
                    "platform": platform,
                    "error": str(result)
                })
            elif result.get("success"):
                successful.append(result)
            else:
                failed.append(result)
        
        print(f"\n{'='*60}")
        print(f"📊 PUBLISHING SUMMARY")
        print(f"{'='*60}")
        print(f" Successful: {len(successful)}/{len(connections)}")
        print(f" Failed: {len(failed)}/{len(connections)}")
        print(f"{'='*60}\n")
        
        return {
            "success": len(successful) > 0,
            "total_platforms": len(connections),
            "successful": len(successful),
            "failed": len(failed),
            "results": successful + failed
        }
    
    @classmethod
    async def validate_platform_connection(
        cls,
        connection: SocialConnection,
        db: Optional[AsyncSession] = None
    ) -> bool:
        """
        Validate if a platform connection is still valid.
        
        Args:
            connection: Social connection to validate
            db: Database session for token refresh
            
        Returns:
            True if valid, False otherwise
        """
        platform = connection.platform.upper()
        service_class = cls.PLATFORM_SERVICES.get(platform)
        
        if not service_class:
            return False
        
        try:
            # Ensure valid token (handles OAuth 1.0a vs 2.0)
            if db:
                access_token = await cls.ensure_valid_token(connection, db)
            else:
                access_token = connection.access_token
            
            # Validate
            return await service_class.validate_token(access_token)
            
        except Exception as e:
            print(f" Validation error for {platform}: {e}")
            return False
    
    @classmethod
    def get_platform_limits(cls, platform: str) -> Dict[str, int]:
        """
        Get media limits for a specific platform.
        
        Args:
            platform: Platform name (TWITTER, FACEBOOK, etc.)
            
        Returns:
            Dict with max_images, max_videos, etc.
        """
        service_class = cls.PLATFORM_SERVICES.get(platform.upper())
        
        if not service_class:
            return {}
        
        return {
            "max_images": service_class.MAX_IMAGES,
            "max_videos": service_class.MAX_VIDEOS,
            "max_video_size_mb": service_class.MAX_VIDEO_SIZE_MB,
            "max_video_duration": service_class.MAX_VIDEO_DURATION_SECONDS
        }
    
    @classmethod
    def get_all_platform_limits(cls) -> Dict[str, Dict[str, int]]:
        """Get limits for all platforms"""
        return {
            platform: cls.get_platform_limits(platform)
            for platform in cls.PLATFORM_SERVICES.keys()
        }