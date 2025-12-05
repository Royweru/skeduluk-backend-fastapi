# app/services/social_service.py
import httpx
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import mimetypes
from pathlib import Path

from .. import models, crud
from ..config import settings
from .oauth_service import OAuthService

class SocialService:
    """Enhanced social media posting service based on Postiz implementation"""
    
    @staticmethod
    async def ensure_valid_token(connection: models.SocialConnection, db: AsyncSession) -> str:
        """Ensure token is valid, refresh if needed"""
        if connection.token_expires_at and connection.token_expires_at < datetime.utcnow():
            print(f"🔄 Token expired for {connection.platform}, refreshing...")
            result = await OAuthService.refresh_access_token(connection, db)
            if not result:
                raise Exception(f"Failed to refresh token for {connection.platform}")
            return result["access_token"]
        return connection.access_token
    
    @staticmethod
    async def publish_to_platform(
        connection: models.SocialConnection,
        content: str,
        image_urls: List[str] = None,
        video_urls: List[str] = None,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """Publish content to a specific social platform"""
        platform = connection.platform.upper()
        
        # Ensure valid token
        if db:
            access_token = await SocialService.ensure_valid_token(connection, db)
        else:
            access_token = connection.access_token
        
        if platform == "TWITTER":
            return await SocialService._post_to_twitter(access_token, content, image_urls, video_urls)
        elif platform == "FACEBOOK":
            return await SocialService._post_to_facebook(access_token, content, image_urls, video_urls)
        elif platform == "INSTAGRAM":
            return await SocialService._post_to_instagram(access_token, content, image_urls, video_urls)
        elif platform == "YOUTUBE":
            return await SocialService._post_to_youtube(access_token, content, video_urls)
        else:
            return {"success": False, "error": f"Unsupported platform: {platform}"}
    
    @staticmethod
    async def _download_media(url: str) -> Optional[bytes]:
        """Download media file from URL"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.content
                return None
        except Exception as e:
            print(f"Error downloading media: {e}")
            return None
    
    # ==================== TWITTER/X ====================
    
    @staticmethod
    async def _post_to_twitter(
        access_token: str,
        content: str,
        image_urls: List[str] = None,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
        """
        Post to Twitter/X using API v2
        Based on Postiz XProvider implementation
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        tweet_data = {"text": content}
        media_ids = []
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Handle video (priority over images)
                if video_urls:
                    video_url = video_urls[0]
                    media_id = await SocialService._upload_twitter_video(
                        access_token, video_url, client
                    )
                    if media_id:
                        media_ids.append(media_id)
                
                # Handle images (only if no video)
                elif image_urls:
                    for image_url in image_urls[:4]:  # Twitter max 4 images
                        media_id = await SocialService._upload_twitter_media(
                            access_token, image_url, "image", client
                        )
                        if media_id:
                            media_ids.append(media_id)
                
                if media_ids:
                    tweet_data["media"] = {"media_ids": media_ids}
                
                # Post tweet
                response = await client.post(
                    "https://api.twitter.com/2/tweets",
                    headers=headers,
                    json=tweet_data
                )
                
                if response.status_code == 201:
                    data = response.json()
                    tweet_id = data["data"]["id"]
                    username = data.get("data", {}).get("author_id", "")
                    
                    return {
                        "success": True,
                        "platform_post_id": tweet_id,
                        "url": f"https://twitter.com/user/status/{tweet_id}"
                    }
                else:
                    error_text = response.text
                    print(f"❌ Twitter post error: {response.status_code} {error_text}")
                    return {
                        "success": False,
                        "error": f"Twitter API error: {error_text}"
                    }
                    
        except Exception as e:
            print(f"❌ Twitter post exception: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def _upload_twitter_media(
        access_token: str,
        media_url: str,
        media_type: str,
        client: httpx.AsyncClient
    ) -> Optional[str]:
        """Upload media to Twitter (image or video init)"""
        try:
            media_data = await SocialService._download_media(media_url)
            if not media_data:
                return None
            
            # Determine media category
            media_category = "tweet_image" if media_type == "image" else "tweet_video"
            
            files = {"media": media_data}
            headers = {"Authorization": f"Bearer {access_token}"}
            
            response = await client.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                headers=headers,
                files=files,
                data={"media_category": media_category}
            )
            
            if response.status_code == 200:
                return response.json().get("media_id_string")
            else:
                print(f"❌ Twitter media upload failed: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Twitter media upload error: {e}")
            return None
    
    @staticmethod
    async def _upload_twitter_video(
        access_token: str,
        video_url: str,
        client: httpx.AsyncClient
    ) -> Optional[str]:
      
        try:
            video_data = await SocialService._download_media(video_url)
            if not video_data:
                return None
            
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # INIT
            init_response = await client.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                headers=headers,
                data={
                    "command": "INIT",
                    "total_bytes": len(video_data),
                    "media_type": "video/mp4",
                    "media_category": "tweet_video"
                }
            )
            
            if init_response.status_code != 200:
                print(f"❌ Video INIT failed: {init_response.text}")
                return None
            
            media_id = init_response.json()["media_id_string"]
            
            # APPEND (chunked)
            chunk_size = 5 * 1024 * 1024  # 5MB chunks
            for i in range(0, len(video_data), chunk_size):
                chunk = video_data[i:i + chunk_size]
                segment_index = i // chunk_size
                
                files = {"media": chunk}
                append_response = await client.post(
                    "https://upload.twitter.com/1.1/media/upload.json",
                    headers=headers,
                    data={
                        "command": "APPEND",
                        "media_id": media_id,
                        "segment_index": segment_index
                    },
                    files=files
                )
                
                if append_response.status_code not in [200, 201, 204]:
                    print(f"❌ Video APPEND failed: {append_response.text}")
                    return None
            
            # FINALIZE
            finalize_response = await client.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                headers=headers,
                data={
                    "command": "FINALIZE",
                    "media_id": media_id
                }
            )
            
            if finalize_response.status_code == 200:
                # Wait for processing
                processing_info = finalize_response.json().get("processing_info")
                if processing_info:
                    await SocialService._wait_for_twitter_video_processing(
                        access_token, media_id, client
                    )
                
                return media_id
            else:
                print(f"❌ Video FINALIZE failed: {finalize_response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Twitter video upload error: {e}")
            return None
    
    @staticmethod
    async def _wait_for_twitter_video_processing(
        access_token: str,
        media_id: str,
        client: httpx.AsyncClient,
        max_wait: int = 300
    ):
        """Wait for Twitter video processing to complete"""
        headers = {"Authorization": f"Bearer {access_token}"}
        waited = 0
        
        while waited < max_wait:
            await asyncio.sleep(5)
            waited += 5
            
            response = await client.get(
                f"https://upload.twitter.com/1.1/media/upload.json?command=STATUS&media_id={media_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                processing_info = data.get("processing_info", {})
                state = processing_info.get("state")
                
                if state == "succeeded":
                    print("✅ Video processing completed")
                    return
                elif state == "failed":
                    print("❌ Video processing failed")
                    return
            else:
                break
    
    # ==================== FACEBOOK ====================
    
    @staticmethod
    async def _post_to_facebook(
        access_token: str,
        content: str,
        image_urls: List[str] = None,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                # Get user's pages
                pages_url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={access_token}"
                pages_response = await client.get(pages_url)
                
                if pages_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to get pages: {pages_response.text}"
                    }
                
                pages_data = pages_response.json()
                if not pages_data.get("data"):
                    return {"success": False, "error": "No Facebook pages found"}
                
                # Use first page
                page = pages_data["data"][0]
                page_id = page["id"]
                page_token = page["access_token"]
                
                # Handle video
                if video_urls:
                    video_url = video_urls[0]
                    video_data = await SocialService._download_media(video_url)
                    
                    if video_data:
                        files = {"source": ("video.mp4", video_data, "video/mp4")}
                        post_data = {
                            "description": content,
                            "access_token": page_token
                        }
                        
                        response = await client.post(
                            f"https://graph-video.facebook.com/v20.0/{page_id}/videos",
                            data=post_data,
                            files=files
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            post_id = result.get("id")
                            return {
                                "success": True,
                                "platform_post_id": post_id,
                                "url": f"https://www.facebook.com/{post_id}"
                            }
                        else:
                            return {
                                "success": False,
                                "error": f"Video upload failed: {response.text}"
                            }
                
                # Handle images or text
                post_data = {
                    "message": content,
                    "access_token": page_token
                }
                
                if image_urls:
                    # Single image
                    if len(image_urls) == 1:
                        post_data["url"] = image_urls[0]
                        post_url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
                    else:
                        # Multiple images - use first for simplicity
                        post_data["url"] = image_urls[0]
                        post_url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
                else:
                    # Text only
                    post_url = f"https://graph.facebook.com/v20.0/{page_id}/feed"
                
                response = await client.post(post_url, data=post_data)
                
                if response.status_code == 200:
                    result = response.json()
                    post_id = result.get("id") or result.get("post_id")
                    return {
                        "success": True,
                        "platform_post_id": post_id,
                        "url": f"https://www.facebook.com/{post_id}"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Facebook post failed: {response.text}"
                    }
                    
        except Exception as e:
            print(f"❌ Facebook post error: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== INSTAGRAM ====================
    
    @staticmethod
    async def _post_to_instagram(
        access_token: str,
        content: str,
        image_urls: List[str] = None,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Get Facebook pages
                pages_url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={access_token}"
                pages_response = await client.get(pages_url)
                
                if pages_response.status_code != 200:
                    return {"success": False, "error": "Failed to get pages"}
                
                pages_data = pages_response.json()
                if not pages_data.get("data"):
                    return {"success": False, "error": "No Facebook pages found"}
                
                page = pages_data["data"][0]
                page_id = page["id"]
                page_token = page["access_token"]
                
                # Get Instagram Business Account
                ig_url = f"https://graph.facebook.com/v20.0/{page_id}?fields=instagram_business_account&access_token={page_token}"
                ig_response = await client.get(ig_url)
                
                if ig_response.status_code != 200:
                    return {"success": False, "error": "Instagram account not found"}
                
                ig_data = ig_response.json()
                ig_account_id = ig_data.get("instagram_business_account", {}).get("id")
                
                if not ig_account_id:
                    return {"success": False, "error": "Instagram Business Account not connected"}
                
                # Create media container
                container_data = {
                    "caption": content,
                    "access_token": page_token
                }
                
                if video_urls:
                    # Instagram Reel
                    container_data["media_type"] = "REELS"
                    container_data["video_url"] = video_urls[0]
                elif image_urls:
                    # Single image or carousel
                    if len(image_urls) == 1:
                        container_data["image_url"] = image_urls[0]
                    else:
                        # For carousel, need to create children first
                        container_data["image_url"] = image_urls[0]
                else:
                    return {"success": False, "error": "Instagram requires media"}
                
                # Create container
                container_url = f"https://graph.facebook.com/v20.0/{ig_account_id}/media"
                container_response = await client.post(container_url, data=container_data)
                
                if container_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Container creation failed: {container_response.text}"
                    }
                
                container_id = container_response.json()["id"]
                
                # Wait for container to be ready (videos need processing)
                if video_urls:
                    await asyncio.sleep(30)  # Wait for video processing
                
                # Publish container
                publish_data = {
                    "creation_id": container_id,
                    "access_token": page_token
                }
                
                publish_url = f"https://graph.facebook.com/v20.0/{ig_account_id}/media_publish"
                publish_response = await client.post(publish_url, data=publish_data)
                
                if publish_response.status_code == 200:
                    result = publish_response.json()
                    post_id = result["id"]
                    return {
                        "success": True,
                        "platform_post_id": post_id,
                        "url": f"https://www.instagram.com/p/{post_id}"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Publish failed: {publish_response.text}"
                    }
                    
        except Exception as e:
            print(f"❌ Instagram post error: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== YOUTUBE ====================
    
    @staticmethod
    async def _post_to_youtube(
        access_token: str,
        content: str,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
      
        if not video_urls:
            return {"success": False, "error": "YouTube requires a video"}
        
        try:
            video_url = video_urls[0]
            video_data = await SocialService._download_media(video_url)
            
            if not video_data:
                return {"success": False, "error": "Failed to download video"}
            
            # Prepare video metadata
            metadata = {
                "snippet": {
                    "title": content[:100],  # Max 100 chars for title
                    "description": content,
                    "categoryId": "22"  # People & Blogs
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False
                }
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Upload video
                files = {"video": ("video.mp4", video_data, "video/mp4")}
                
                response = await client.post(
                    "https://www.googleapis.com/upload/youtube/v3/videos",
                    params={
                        "part": "snippet,status",
                        "uploadType": "multipart"
                    },
                    headers=headers,
                    data={"resource": str(metadata)},
                    files=files
                )
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    video_id = data.get("id")
                    return {
                        "success": True,
                        "platform_post_id": video_id,
                        "url": f"https://www.youtube.com/watch?v={video_id}"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"YouTube upload failed: {response.text}"
                    }
                    
        except Exception as e:
            print(f"❌ YouTube upload error: {e}")
            return {"success": False, "error": str(e)}