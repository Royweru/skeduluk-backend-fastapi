# app/services/platforms/facebook.py
"""
Facebook platform service for posting to Facebook Pages.
Requires a selected Facebook Page with page access token.
"""

import httpx
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from .base_platform import BasePlatformService
from app import models


class FacebookService(BasePlatformService):
    """Facebook platform service implementation"""
    
    PLATFORM_NAME = "FACEBOOK"
    MAX_IMAGES = 10
    MAX_VIDEOS = 1
    MAX_VIDEO_SIZE_MB = 4096  # 4GB
    MAX_VIDEO_DURATION_SECONDS = 240  # 4 minutes
    
    API_BASE = "https://graph.facebook.com/v20.0"
    VIDEO_API_BASE = "https://graph-video.facebook.com/v20.0"
    
    @classmethod
    async def post(
        cls,
        access_token: str,
        content: str,
        image_urls: Optional[List[str]] = None,
        video_urls: Optional[List[str]] = None,
        connection: Optional[models.SocialConnection] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Post to Facebook Page.
        
        Args:
            access_token: User access token (used to get page info)
            content: Post text
            image_urls: Image URLs
            video_urls: Video URLs
            connection: SocialConnection object with page info
        """
        print(f"📘 Facebook: Starting post creation")
        
        # Check if page is selected
        if not connection or not connection.facebook_page_id:
            return cls.format_error_response(
                "No Facebook Page selected. Select a page in Settings."
            )
        
        page_id = connection.facebook_page_id
        page_token = connection.facebook_page_access_token
        page_name = connection.facebook_page_name
        
        print(f"📘 Facebook: Posting to page {page_name} (ID: {page_id})")
        
        # Validate media
        error = cls.validate_media_count(image_urls, video_urls)
        if error:
            return cls.format_error_response(error)
        
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                # Handle video upload
                if video_urls:
                    return await cls._post_video(
                        client, page_id, page_token, content, video_urls[0]
                    )
                
                # Handle image or text post
                post_data = {
                    "message": content,
                    "access_token": page_token
                }
                
                if image_urls and len(image_urls) > 0:
                    # Post with image
                    post_data["url"] = image_urls[0]
                    post_url = f"{cls.API_BASE}/{page_id}/photos"
                else:
                    # Text-only post
                    post_url = f"{cls.API_BASE}/{page_id}/feed"
                
                response = await client.post(post_url, data=post_data)
                
                if response.status_code == 200:
                    result = response.json()
                    post_id = result.get("id") or result.get("post_id")
                    
                    print(f"✅ Facebook: Post created successfully")
                    
                    return cls.format_success_response(
                        post_id,
                        f"https://www.facebook.com/{page_name}/posts/{post_id.split('_')[1] if '_' in post_id else post_id}"
                    )
                else:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", response.text)
                    return cls.format_error_response(f"Post failed: {error_msg}")
                    
        except Exception as e:
            print(f"❌ Facebook post error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
    @classmethod
    async def _post_video(
        cls,
        client: httpx.AsyncClient,
        page_id: str,
        page_token: str,
        content: str,
        video_url: str
    ) -> Dict[str, Any]:
        """Upload video to Facebook Page"""
        print(f"📘 Facebook: Uploading video")
        
        # Download video
        video_data = await cls.download_media(video_url, timeout=180)
        if not video_data:
            return cls.format_error_response("Failed to download video")
        
        print(f"📘 Facebook: Video size: {len(video_data) / (1024*1024):.2f} MB")
        
        # Upload video
        files = {"source": ("video.mp4", video_data, "video/mp4")}
        post_data = {
            "description": content,
            "access_token": page_token
        }
        
        response = await client.post(
            f"{cls.VIDEO_API_BASE}/{page_id}/videos",
            data=post_data,
            files=files
        )
        
        if response.status_code == 200:
            result = response.json()
            post_id = result.get("id")
            
            print(f"✅ Facebook: Video uploaded successfully")
            
            return cls.format_success_response(
                post_id,
                f"https://www.facebook.com/{page_id}/posts/{post_id}"
            )
        else:
            return cls.format_error_response(f"Video upload failed: {response.text}")
    
    @classmethod
    async def validate_token(cls, access_token: str) -> bool:
        """Validate Facebook access token"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{cls.API_BASE}/me",
                    params={"access_token": access_token}
                )
                return response.status_code == 200
        except:
            return False
    
    @classmethod
    async def get_pages(cls, access_token: str) -> List[Dict[str, Any]]:
        """Get list of Facebook Pages user can manage"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{cls.API_BASE}/me/accounts",
                    params={
                        "access_token": access_token,
                        "fields": "id,name,category,access_token,picture"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    pages = data.get("data", [])
                    
                    return [
                        {
                            "id": page["id"],
                            "name": page["name"],
                            "category": page.get("category", "Unknown"),
                            "access_token": page["access_token"],
                            "picture_url": page.get("picture", {}).get("data", {}).get("url")
                        }
                        for page in pages
                    ]
            return []
        except Exception as e:
            print(f"❌ Error fetching Facebook pages: {e}")
            return []