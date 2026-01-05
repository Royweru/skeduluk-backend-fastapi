# app/services/platforms/linkedin.py
"""
LinkedIn platform service with PROPER video upload support.
âœ… FIXED: Videos now check processing status before posting
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
    
    # âœ… VIDEO PROCESSING CONFIGURATION
    MAX_PROCESSING_WAIT_TIME = 300  # 5 minutes max wait
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
        Post content to LinkedIn with images or video.
        
        âœ… FIXED: Now properly waits for video processing to complete
        """
        print(f"ðŸ'¼ LinkedIn: Starting post creation")
        
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
                
                print(f"ðŸ'¼ LinkedIn: Author URN: {author_urn}")
                
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
            print(f"âŒ LinkedIn post error: {e}")
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
            
            print(f"âŒ Failed to get profile: {response.status_code} - {response.text}")
            return None
            
        except Exception as e:
            print(f"âŒ Error getting author URN: {e}")
            return None
    
    @classmethod
    async def _check_asset_status(
        cls,
        client: httpx.AsyncClient,
        access_token: str,
        asset_urn: str
    ) -> Optional[str]:
        """
        âœ… NEW: Check if video asset has finished processing
        
        Returns:
            - "AVAILABLE" if ready to use
            - "PROCESSING" if still processing
            - "PROCESSING_FAILED" if upload failed
            - None if can't determine status
        """
        try:
            # Extract asset ID from URN (format: urn:li:digitalmediaAsset:ASSET_ID)
            asset_id = asset_urn.split(":")[-1]
            
            response = await client.get(
                f"{cls.API_BASE}/assets/{asset_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Restli-Protocol-Version": "2.0.0"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check recipe status
                recipes = data.get("recipes", [])
                if recipes:
                    recipe_status = recipes[0].get("status", "UNKNOWN")
                    print(f"ðŸ'¼ LinkedIn: Asset status = {recipe_status}")
                    return recipe_status
                
                # Fallback to overall status
                return data.get("status", "UNKNOWN")
            
            print(f"âš ï¸ LinkedIn: Could not check asset status: {response.status_code}")
            return None
            
        except Exception as e:
            print(f"âŒ Error checking asset status: {e}")
            return None
    
    @classmethod
    async def _wait_for_video_processing(
        cls,
        client: httpx.AsyncClient,
        access_token: str,
        asset_urn: str
    ) -> bool:
        """
        âœ… NEW: Wait for LinkedIn to finish processing the video
        
        This is THE CRITICAL FIX - LinkedIn videos are processed asynchronously!
        According to LinkedIn docs: "If the post is created before confirming 
        upload success and the video upload fails to process, the post won't 
        be visible to members."
        
        Returns:
            True if video is ready, False if failed or timeout
        """
        print(f"ðŸ'¼ LinkedIn: Waiting for video processing to complete...")
        print(f"   (This can take 1-5 minutes depending on video size)")
        
        start_time = asyncio.get_event_loop().time()
        elapsed = 0
        
        while elapsed < cls.MAX_PROCESSING_WAIT_TIME:
            # Check status
            status = await cls._check_asset_status(client, access_token, asset_urn)
            
            if status == "AVAILABLE":
                print(f"✅ LinkedIn: Video processing complete! (took {elapsed:.1f}s)")
                return True
            
            elif status == "PROCESSING_FAILED":
                print(f"âŒ LinkedIn: Video processing FAILED")
                return False
            
            elif status == "PROCESSING":
                # Still processing, wait and check again
                print(f"   âłï¸ Still processing... ({elapsed:.1f}s elapsed)")
                await asyncio.sleep(cls.STATUS_CHECK_INTERVAL)
                elapsed = asyncio.get_event_loop().time() - start_time
                continue
            
            else:
                # Unknown status, wait a bit and try again
                print(f"   âš ï¸ Unknown status: {status}, retrying...")
                await asyncio.sleep(cls.STATUS_CHECK_INTERVAL)
                elapsed = asyncio.get_event_loop().time() - start_time
        
        # Timeout
        print(f"⏰ LinkedIn: Video processing timeout after {cls.MAX_PROCESSING_WAIT_TIME}s")
        return False
    
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
        âœ… FIXED: Now properly waits for video processing
        """
        print(f"ðŸ'¼ LinkedIn: Uploading video from {video_url}")
        
        try:
            # Download video
            video_data = await cls.download_media(video_url, timeout=120)
            if not video_data:
                return cls.format_error_response("Failed to download video")
            
            video_size = len(video_data)
            video_size_mb = video_size / (1024*1024)
            print(f"ðŸ'¼ LinkedIn: Video size: {video_size_mb:.2f} MB")
            
            # Check video size limit
            if video_size_mb > cls.MAX_VIDEO_SIZE_MB:
                return cls.format_error_response(
                    f"Video too large: {video_size_mb:.2f}MB (max: {cls.MAX_VIDEO_SIZE_MB}MB)"
                )
            
            # Step 1: Register video upload
            print(f"ðŸ'¼ LinkedIn: Registering video upload...")
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
            
            print(f"ðŸ'¼ LinkedIn: Video URN: {video_urn}")
            print(f"ðŸ'¼ LinkedIn: Upload URL obtained")
            
            # Step 2: Upload video data
            print(f"ðŸ'¼ LinkedIn: Uploading video data ({video_size_mb:.2f}MB)...")
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
            
            print(f"✅ LinkedIn: Video uploaded successfully")
            
            # âœ… CRITICAL FIX: Wait for LinkedIn to process the video
            # This is what was missing! LinkedIn processes videos asynchronously
            # and if we create the post before processing completes, 
            # the video won't appear in the post!
            video_ready = await cls._wait_for_video_processing(
                client, access_token, video_urn
            )
            
            if not video_ready:
                return cls.format_error_response(
                    "Video upload succeeded but processing failed or timed out. "
                    "LinkedIn needs time to process videos. Try again or use a smaller video."
                )
            
            # Step 3: Create post with video (now that it's READY)
            post_data = {
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": content},
                        "shareMediaCategory": "VIDEO",
                        "media": [{
                            "status": "READY",  # âœ… Now we KNOW it's ready!
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
            
            print(f"ðŸ'¼ LinkedIn: Creating UGC post with processed video...")
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
                print(f"✅ LinkedIn: Video post created successfully!")
                print(f"   Post ID: {post_id}")
                return cls.format_success_response(
                    post_id,
                    f"https://www.linkedin.com/feed/update/{post_id}/"
                )
            else:
                error_text = post_response.text
                print(f"âŒ LinkedIn: Post creation failed: {error_text}")
                return cls.format_error_response(f"Post creation failed: {error_text}")
            
        except Exception as e:
            print(f"âŒ LinkedIn video upload error: {e}")
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
        print(f"ðŸ'¼ LinkedIn: Uploading {len(image_urls)} images")
        
        uploaded_assets = []
        
        for idx, image_url in enumerate(image_urls[:cls.MAX_IMAGES], 1):
            try:
                print(f"ðŸ'¼ LinkedIn: Processing image {idx}/{min(len(image_urls), cls.MAX_IMAGES)}")
                
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
                    print(f"âŒ Failed to register image {idx}: {register_response.text}")
                    continue
                
                register_data = register_response.json()
                upload_url = register_data["value"]["uploadMechanism"][
                    "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                asset = register_data["value"]["asset"]
                
                # Download image
                image_data = await cls.download_media(image_url)
                if not image_data:
                    print(f"âŒ Failed to download image {idx}")
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
                    print(f"✅ Image {idx} uploaded: {asset}")
                else:
                    print(f"âŒ Failed to upload image {idx}: {upload_response.status_code}")
                
            except Exception as e:
                print(f"âŒ Failed to upload image {idx}: {e}")
                continue
        
        if not uploaded_assets:
            return cls.format_error_response("Failed to upload any images")
        
        print(f"ðŸ'¼ LinkedIn: Successfully uploaded {len(uploaded_assets)}/{len(image_urls)} images")
        
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
                            "title": {"text": f"Image {i+1}"}
                        }
                        for i, asset in enumerate(uploaded_assets)
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
            print(f"✅ LinkedIn: Image post created successfully!")
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