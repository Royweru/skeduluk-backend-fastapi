# app/services/platforms/instagram.py
"""
Instagram platform service for posting images and reels.
Uses Instagram Graph API through Facebook.
"""

import httpx
import asyncio
from typing import Dict, List, Any, Optional
from .base_platform import BasePlatformService


class InstagramService(BasePlatformService):
    """Instagram platform service implementation"""
    
    PLATFORM_NAME = "INSTAGRAM"
    MAX_IMAGES = 10  # For carousel
    MAX_VIDEOS = 1   # For reels
    MAX_VIDEO_SIZE_MB = 100
    MAX_VIDEO_DURATION_SECONDS = 60
    
    API_BASE = "https://graph.facebook.com/v20.0"
    
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
        Post to Instagram.
        Requires Instagram Business Account connected to Facebook Page.
        
        Args:
            access_token: Facebook access token
            content: Caption text
            image_urls: Image URLs (for posts/carousel)
            video_urls: Video URLs (for reels)
        """
        print(f"📸 Instagram: Starting post creation")
        
        # Validate media
        error = cls.validate_media_count(image_urls, video_urls)
        if error:
            return cls.format_error_response(error)
        
        # Instagram requires media
        if not image_urls and not video_urls:
            return cls.format_error_response("Instagram requires media (image or video)")
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Get Instagram Business Account
                ig_account_id, page_token = await cls._get_instagram_account(
                    client, access_token
                )
                
                if not ig_account_id:
                    return cls.format_error_response(
                        "Instagram Business Account not connected"
                    )
                
                print(f"📸 Instagram: Account ID: {ig_account_id}")
                
                # Handle video (Reel)
                if video_urls:
                    return await cls._post_reel(
                        client, ig_account_id, page_token, content, video_urls[0]
                    )
                
                # Handle image(s)
                if image_urls:
                    if len(image_urls) == 1:
                        return await cls._post_single_image(
                            client, ig_account_id, page_token, content, image_urls[0]
                        )
                    else:
                        return await cls._post_carousel(
                            client, ig_account_id, page_token, content, image_urls
                        )
                
        except Exception as e:
            print(f"❌ Instagram post error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
    @classmethod
    async def _get_instagram_account(
        cls,
        client: httpx.AsyncClient,
        access_token: str
    ) -> tuple[Optional[str], Optional[str]]:
        """Get Instagram Business Account ID and page token"""
        try:
            # Get Facebook pages
            pages_response = await client.get(
                f"{cls.API_BASE}/me/accounts",
                params={"access_token": access_token}
            )
            
            if pages_response.status_code != 200:
                return None, None
            
            pages_data = pages_response.json()
            pages = pages_data.get("data", [])
            
            if not pages:
                return None, None
            
            # Get first page (or should we let user select?)
            page = pages[0]
            page_id = page["id"]
            page_token = page["access_token"]
            
            # Get Instagram account from page
            ig_response = await client.get(
                f"{cls.API_BASE}/{page_id}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": page_token
                }
            )
            
            if ig_response.status_code != 200:
                return None, None
            
            ig_data = ig_response.json()
            ig_account_id = ig_data.get("instagram_business_account", {}).get("id")
            
            return ig_account_id, page_token
            
        except Exception as e:
            print(f"❌ Error getting Instagram account: {e}")
            return None, None
    
    @classmethod
    async def _post_single_image(
        cls,
        client: httpx.AsyncClient,
        ig_account_id: str,
        page_token: str,
        caption: str,
        image_url: str
    ) -> Dict[str, Any]:
        """Post single image to Instagram"""
        print(f"📸 Instagram: Posting single image")
        
        # Create container
        container_data = {
            "image_url": image_url,
            "caption": caption,
            "access_token": page_token
        }
        
        container_response = await client.post(
            f"{cls.API_BASE}/{ig_account_id}/media",
            data=container_data
        )
        
        if container_response.status_code != 200:
            return cls.format_error_response(
                f"Container creation failed: {container_response.text}"
            )
        
        container_id = container_response.json()["id"]
        
        # Publish container
        await asyncio.sleep(2)  # Wait for processing
        
        publish_response = await client.post(
            f"{cls.API_BASE}/{ig_account_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": page_token
            }
        )
        
        if publish_response.status_code == 200:
            result = publish_response.json()
            post_id = result["id"]
            
            print(f"✅ Instagram: Image posted successfully")
            
            return cls.format_success_response(
                post_id,
                f"https://www.instagram.com/p/{post_id}"
            )
        else:
            return cls.format_error_response(f"Publish failed: {publish_response.text}")
    
    @classmethod
    async def _post_carousel(
        cls,
        client: httpx.AsyncClient,
        ig_account_id: str,
        page_token: str,
        caption: str,
        image_urls: List[str]
    ) -> Dict[str, Any]:
        """Post carousel (multiple images) to Instagram"""
        print(f"📸 Instagram: Posting carousel with {len(image_urls)} images")
        
        # Create containers for each image
        children_ids = []
        
        for image_url in image_urls[:cls.MAX_IMAGES]:
            container_response = await client.post(
                f"{cls.API_BASE}/{ig_account_id}/media",
                data={
                    "image_url": image_url,
                    "is_carousel_item": True,
                    "access_token": page_token
                }
            )
            
            if container_response.status_code == 200:
                children_ids.append(container_response.json()["id"])
        
        if not children_ids:
            return cls.format_error_response("Failed to create carousel items")
        
        # Create carousel container
        carousel_response = await client.post(
            f"{cls.API_BASE}/{ig_account_id}/media",
            data={
                "media_type": "CAROUSEL",
                "caption": caption,
                "children": ",".join(children_ids),
                "access_token": page_token
            }
        )
        
        if carousel_response.status_code != 200:
            return cls.format_error_response(
                f"Carousel creation failed: {carousel_response.text}"
            )
        
        carousel_id = carousel_response.json()["id"]
        
        # Publish carousel
        await asyncio.sleep(3)
        
        publish_response = await client.post(
            f"{cls.API_BASE}/{ig_account_id}/media_publish",
            data={
                "creation_id": carousel_id,
                "access_token": page_token
            }
        )
        
        if publish_response.status_code == 200:
            result = publish_response.json()
            post_id = result["id"]
            
            print(f"✅ Instagram: Carousel posted successfully")
            
            return cls.format_success_response(
                post_id,
                f"https://www.instagram.com/p/{post_id}"
            )
        else:
            return cls.format_error_response(f"Publish failed: {publish_response.text}")
    
    @classmethod
    async def _post_reel(
        cls,
        client: httpx.AsyncClient,
        ig_account_id: str,
        page_token: str,
        caption: str,
        video_url: str
    ) -> Dict[str, Any]:
        """Post reel (video) to Instagram"""
        print(f"📸 Instagram: Posting reel")
        
        # Create reel container
        container_data = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": page_token
        }
        
        container_response = await client.post(
            f"{cls.API_BASE}/{ig_account_id}/media",
            data=container_data
        )
        
        if container_response.status_code != 200:
            return cls.format_error_response(
                f"Reel container creation failed: {container_response.text}"
            )
        
        container_id = container_response.json()["id"]
        
        # Wait for video processing
        print(f"📸 Instagram: Waiting for video processing...")
        await asyncio.sleep(30)  # Reels need more time
        
        # Publish reel
        publish_response = await client.post(
            f"{cls.API_BASE}/{ig_account_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": page_token
            }
        )
        
        if publish_response.status_code == 200:
            result = publish_response.json()
            post_id = result["id"]
            
            print(f"✅ Instagram: Reel posted successfully")
            
            return cls.format_success_response(
                post_id,
                f"https://www.instagram.com/reel/{post_id}"
            )
        else:
            return cls.format_error_response(f"Publish failed: {publish_response.text}")
    
    @classmethod
    async def validate_token(cls, access_token: str) -> bool:
        """Validate Instagram/Facebook access token"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                ig_account_id, _ = await cls._get_instagram_account(client, access_token)
                return ig_account_id is not None
        except:
            return False