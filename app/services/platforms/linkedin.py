# app/services/platforms/linkedin.py
"""
LinkedIn platform service with full video and image upload support.
Uses LinkedIn UGC (User Generated Content) API v2.
"""

import httpx
import asyncio
from typing import Dict, List, Any, Optional
from .base_platform import BasePlatformService


class LinkedInService(BasePlatformService):
    """LinkedIn platform service implementation"""
    
    PLATFORM_NAME = "LINKEDIN"
    MAX_IMAGES = 9
    MAX_VIDEOS = 1
    MAX_VIDEO_SIZE_MB = 5120  # 5GB
    MAX_VIDEO_DURATION_SECONDS = 600  # 10 minutes
    
    API_BASE = "https://api.linkedin.com/v2"
    
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
        Post content to LinkedIn with images or video.
        
        LinkedIn video upload process:
        1. Get author URN (user profile)
        2. Register video upload
        3. Upload video chunks
        4. Finalize upload
        5. Create UGC post with video
        """
        print(f"💼 LinkedIn: Starting post creation")
        
        # Validate media counts
        error = cls.validate_media_count(image_urls, video_urls)
        if error:
            return cls.format_error_response(error)
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Step 1: Get user profile (author URN)
                author_urn = await cls._get_author_urn(client, access_token)
                if not author_urn:
                    return cls.format_error_response("Failed to get user profile")
                
                print(f"💼 LinkedIn: Author URN: {author_urn}")
                
                # Step 2: Handle video upload if present
                if video_urls and len(video_urls) > 0:
                    return await cls._post_with_video(
                        client, access_token, author_urn, content, video_urls[0]
                    )
                
                # Step 3: Handle image upload if present
                if image_urls and len(image_urls) > 0:
                    return await cls._post_with_images(
                        client, access_token, author_urn, content, image_urls
                    )
                
                # Step 4: Text-only post
                return await cls._post_text_only(
                    client, access_token, author_urn, content
                )
                
        except Exception as e:
            print(f"❌ LinkedIn post error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
    @classmethod
    async def _get_author_urn(cls, client: httpx.AsyncClient, access_token: str) -> Optional[str]:
        """Get LinkedIn user profile URN"""
        try:
            response = await client.get(
                f"{cls.API_BASE}/userinfo",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Restli-Protocol-Version": "2.0.0"
                }
            )
            
            if response.status_code == 200:
                profile = response.json()
                return f"urn:li:person:{profile['sub']}"
            
            print(f"❌ Failed to get profile: {response.status_code} - {response.text}")
            return None
            
        except Exception as e:
            print(f"❌ Error getting author URN: {e}")
            return None
    
    @classmethod
    async def _post_with_video(
        cls,
        client: httpx.AsyncClient,
        access_token: str,
        author_urn: str,
        content: str,
        video_url: str
    ) -> Dict[str, Any]:
        """
        Post with video to LinkedIn.
        Uses the video upload API with proper chunked upload.
        """
        print(f"💼 LinkedIn: Uploading video from {video_url}")
        
        try:
            # Download video
            video_data = await cls.download_media(video_url, timeout=120)
            if not video_data:
                return cls.format_error_response("Failed to download video")
            
            video_size = len(video_data)
            print(f"💼 LinkedIn: Video size: {video_size / (1024*1024):.2f} MB")
            
            # Step 1: Register video upload
            print(f"💼 LinkedIn: Registering video upload...")
            register_response = await client.post(
                f"{cls.API_BASE}/assets?action=registerUpload",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0"
                },
                json={
                    "registerUploadRequest": {
                        "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
                        "owner": author_urn,
                        "serviceRelationships": [{
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }]
                    }
                }
            )
            
            if register_response.status_code not in [200, 201]:
                return cls.format_error_response(
                    f"Video registration failed: {register_response.text}"
                )
            
            register_data = register_response.json()
            upload_url = register_data["value"]["uploadMechanism"][
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
            video_urn = register_data["value"]["asset"]
            
            print(f"💼 LinkedIn: Video URN: {video_urn}")
            print(f"💼 LinkedIn: Upload URL obtained")
            
            # Step 2: Upload video
            print(f"💼 LinkedIn: Uploading video data...")
            upload_response = await client.put(
                upload_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/octet-stream"
                },
                content=video_data
            )
            
            if upload_response.status_code not in [200, 201]:
                return cls.format_error_response(
                    f"Video upload failed: {upload_response.text}"
                )
            
            print(f"💼 LinkedIn: Video uploaded successfully")
            
            # Step 3: Wait for video processing (LinkedIn needs time)
            print(f"💼 LinkedIn: Waiting for video processing...")
            await asyncio.sleep(10)  # Give LinkedIn time to process
            
            # Step 4: Create post with video
            post_data = {
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": content},
                        "shareMediaCategory": "VIDEO",
                        "media": [{
                            "status": "READY",
                            "description": {"text": content[:200]},
                            "media": video_urn,
                            "title": {"text": "Video"}
                        }]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            print(f"💼 LinkedIn: Creating UGC post with video...")
            post_response = await client.post(
                f"{cls.API_BASE}/ugcPosts",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0"
                },
                json=post_data
            )
            
            if post_response.status_code in [200, 201]:
                result = post_response.json()
                post_id = result.get("id", "")
                print(f"✅ LinkedIn: Video post created successfully")
                return cls.format_success_response(
                    post_id,
                    f"https://www.linkedin.com/feed/update/{post_id}/"
                )
            else:
                return cls.format_error_response(
                    f"Post creation failed: {post_response.text}"
                )
            
        except Exception as e:
            print(f"❌ LinkedIn video upload error: {e}")
            import traceback
            traceback.print_exc()
            return cls.format_error_response(str(e))
    
    @classmethod
    async def _post_with_images(
        cls,
        client: httpx.AsyncClient,
        access_token: str,
        author_urn: str,
        content: str,
        image_urls: List[str]
    ) -> Dict[str, Any]:
        """Post with images to LinkedIn"""
        print(f"💼 LinkedIn: Uploading {len(image_urls)} images")
        
        uploaded_assets = []
        
        for image_url in image_urls[:cls.MAX_IMAGES]:
            try:
                # Register upload
                register_response = await client.post(
                    f"{cls.API_BASE}/assets?action=registerUpload",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0"
                    },
                    json={
                        "registerUploadRequest": {
                            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                            "owner": author_urn,
                            "serviceRelationships": [{
                                "relationshipType": "OWNER",
                                "identifier": "urn:li:userGeneratedContent"
                            }]
                        }
                    }
                )
                
                if register_response.status_code not in [200, 201]:
                    print(f"❌ Failed to register image: {register_response.text}")
                    continue
                
                register_data = register_response.json()
                upload_url = register_data["value"]["uploadMechanism"][
                    "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                asset = register_data["value"]["asset"]
                
                # Download image
                image_data = await cls.download_media(image_url)
                if not image_data:
                    continue
                
                # Upload image
                upload_response = await client.post(
                    upload_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "image/jpeg"
                    },
                    content=image_data
                )
                
                if upload_response.status_code in [200, 201]:
                    uploaded_assets.append(asset)
                    print(f"✅ Image uploaded: {asset}")
                
            except Exception as e:
                print(f"❌ Failed to upload image: {e}")
                continue
        
        if not uploaded_assets:
            return cls.format_error_response("Failed to upload any images")
        
        # Create post with images
        post_data = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "description": {"text": content[:200]},
                            "media": asset,
                            "title": {"text": "Image"}
                        }
                        for asset in uploaded_assets
                    ]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        response = await client.post(
            f"{cls.API_BASE}/ugcPosts",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            },
            json=post_data
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            post_id = result.get("id", "")
            return cls.format_success_response(
                post_id,
                f"https://www.linkedin.com/feed/update/{post_id}/"
            )
        else:
            return cls.format_error_response(f"Post failed: {response.text}")
    
    @classmethod
    async def _post_text_only(
        cls,
        client: httpx.AsyncClient,
        access_token: str,
        author_urn: str,
        content: str
    ) -> Dict[str, Any]:
        """Post text-only content to LinkedIn"""
        post_data = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        response = await client.post(
            f"{cls.API_BASE}/ugcPosts",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            },
            json=post_data
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            post_id = result.get("id", "")
            return cls.format_success_response(
                post_id,
                f"https://www.linkedin.com/feed/update/{post_id}/"
            )
        else:
            return cls.format_error_response(f"Post failed: {response.text}")
    
    @classmethod
    async def validate_token(cls, access_token: str) -> bool:
        """Validate LinkedIn access token"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{cls.API_BASE}/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                return response.status_code == 200
        except:
            return False