# app/services/platforms/linkedin.py
"""
LinkedIn Platform Implementation
✅ FIXED: Proper video upload using feedshare-video recipe
"""
from typing import Dict, List, Optional, Any
import httpx
from .base import BasePlatform


class LinkedIn(BasePlatform):
    """
    LinkedIn posting implementation with full video support
    
    Key features:
    - Text-only posts
    - Posts with images (up to 9 images)
    - Posts with videos (single video)
    - Proper video upload using feedshare-video recipe
    """
    
    # Platform constants
    MAX_CONTENT_LENGTH = 3000
    MAX_IMAGES = 9
    MAX_VIDEOS = 1
    
    def __init__(self):
        super().__init__("LinkedIn")
        self.api_base = "https://api.linkedin.com/v2"
    
    async def post(
        self,
        access_token: str,
        content: str,
        image_urls: Optional[List[str]] = None,
        video_urls: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Post to LinkedIn with text, images, or video
        
        LinkedIn Flow:
        1. Get user profile
        2. Register media upload (if media present)
        3. Upload media to LinkedIn
        4. Create UGC post with media references
        """
        self.log_start()
        
        try:
            # Validate content
            if not self.validate_content(content, self.MAX_CONTENT_LENGTH):
                return {
                    "success": False,
                    "error": f"Content exceeds {self.MAX_CONTENT_LENGTH} characters"
                }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Step 1: Get user profile
                author_id = await self._get_author_id(client, access_token)
                if not author_id:
                    return {"success": False, "error": "Failed to fetch LinkedIn profile"}
                
                # Step 2: Prepare post data
                post_data = {
                    "author": author_id,
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": content},
                            "shareMediaCategory": "NONE"  # Will change if media present
                        }
                    },
                    "visibility": {
                        "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                    }
                }
                
                # Step 3: Handle video upload (FIXED!)
                if video_urls and len(video_urls) > 0:
                    print(f"🎥 Uploading video to LinkedIn...")
                    video_asset = await self._upload_video(
                        client, 
                        access_token,
                        video_urls[0],
                        author_id
                    )
                    
                    if video_asset:
                        # Add video to post
                        post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "VIDEO"
                        post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                            {
                                "status": "READY",
                                "description": {"text": content[:200]},
                                "media": video_asset,
                                "title": {"text": "Video"}
                            }
                        ]
                        print(f"✅ Video added to post")
                    else:
                        return {"success": False, "error": "Failed to upload video to LinkedIn"}
                
                # Step 4: Handle image upload
                elif image_urls and len(image_urls) > 0:
                    print(f"📸 Uploading {len(image_urls)} image(s) to LinkedIn...")
                    uploaded_assets = await self._upload_images(
                        client,
                        access_token,
                        image_urls,
                        author_id,
                        content
                    )
                    
                    if uploaded_assets:
                        post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
                        post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = uploaded_assets
                        print(f"✅ {len(uploaded_assets)} image(s) added to post")
                
                # Step 5: Create the post
                response = await client.post(
                    f"{self.api_base}/ugcPosts",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0"
                    },
                    json=post_data
                )
                
                print(f"💼 Response status: {response.status_code}")
                
                if response.status_code in [200, 201]:
                    try:
                        result = response.json()
                        post_id = result.get("id", "success")
                        self.log_success(post_id)
                        return {
                            "success": True,
                            "platform_post_id": post_id,
                            "url": f"https://www.linkedin.com/feed/update/{post_id}/"
                        }
                    except:
                        # Sometimes LinkedIn returns empty body on success
                        return {
                            "success": True,
                            "platform_post_id": "success",
                            "url": "https://www.linkedin.com/feed/"
                        }
                else:
                    error_msg = response.text
                    self.log_error(f"Status {response.status_code}: {error_msg}")
                    return {
                        "success": False,
                        "error": f"LinkedIn API error: {response.status_code} - {error_msg[:200]}"
                    }
        
        except Exception as e:
            self.log_error(str(e))
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def _get_author_id(self, client: httpx.AsyncClient, access_token: str) -> Optional[str]:
        """Get LinkedIn user profile to get author URN"""
        try:
            print("💼 Fetching LinkedIn profile...")
            response = await client.get(
                f"{self.api_base}/userinfo",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Restli-Protocol-Version": "2.0.0"
                }
            )
            
            if response.status_code == 200:
                profile = response.json()
                author_id = f"urn:li:person:{profile['sub']}"
                print(f"✅ Profile fetched - Author: {author_id}")
                return author_id
            else:
                print(f"❌ Failed to fetch profile: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error fetching profile: {e}")
            return None
    
    async def _upload_video(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        video_url: str,
        author_id: str
    ) -> Optional[str]:
        """
        Upload video to LinkedIn
        
        ✅ FIXED: Uses feedshare-video recipe instead of feedshare-image
        
        Returns:
            str: Video asset URN if successful, None otherwise
        """
        try:
            # Step 1: Register video upload (CRITICAL FIX!)
            print(f"💼 Registering video upload...")
            register_response = await client.post(
                f"{self.api_base}/assets?action=registerUpload",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0"
                },
                json={
                    "registerUploadRequest": {
                        "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],  # ✅ VIDEO recipe!
                        "owner": author_id,
                        "serviceRelationships": [{
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }]
                    }
                }
            )
            
            if register_response.status_code != 200:
                print(f"❌ Failed to register video upload: {register_response.text}")
                return None
            
            register_data = register_response.json()
            
            if "value" not in register_data or "uploadMechanism" not in register_data["value"]:
                print(f"❌ Invalid register response: {register_data}")
                return None
            
            upload_url = register_data["value"]["uploadMechanism"][
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
            asset = register_data["value"]["asset"]
            
            print(f"✅ Video upload registered: {asset}")
            
            # Step 2: Download video from Cloudinary
            print(f"📥 Downloading video from: {video_url}")
            video_data = await self.download_media(video_url)
            if not video_data:
                return None
            
            # Step 3: Upload video to LinkedIn
            print(f"💼 Uploading video to LinkedIn...")
            upload_response = await client.put(  # ✅ PUT for binary upload
                upload_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "video/mp4"  # ✅ Correct content type
                },
                content=video_data
            )
            
            if upload_response.status_code in [200, 201]:
                print(f"✅ Video uploaded successfully: {asset}")
                return asset
            else:
                print(f"❌ Video upload failed: {upload_response.status_code}")
                print(f"Response: {upload_response.text}")
                return None
        
        except Exception as e:
            print(f"❌ Error uploading video: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _upload_images(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        image_urls: List[str],
        author_id: str,
        content: str
    ) -> List[Dict[str, Any]]:
        """
        Upload multiple images to LinkedIn
        
        Returns:
            List of media objects ready for UGC post
        """
        uploaded_assets = []
        
        for image_url in image_urls[:self.MAX_IMAGES]:
            try:
                # Register image upload
                register_response = await client.post(
                    f"{self.api_base}/assets?action=registerUpload",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0"
                    },
                    json={
                        "registerUploadRequest": {
                            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                            "owner": author_id,
                            "serviceRelationships": [{
                                "relationshipType": "OWNER",
                                "identifier": "urn:li:userGeneratedContent"
                            }]
                        }
                    }
                )
                
                if register_response.status_code != 200:
                    print(f"❌ Failed to register image upload")
                    continue
                
                register_data = register_response.json()
                
                if "value" not in register_data or "uploadMechanism" not in register_data["value"]:
                    continue
                
                upload_url = register_data["value"]["uploadMechanism"][
                    "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                asset = register_data["value"]["asset"]
                
                # Download image
                image_data = await self.download_media(image_url)
                if not image_data:
                    continue
                
                # Upload to LinkedIn
                upload_response = await client.put(
                    upload_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "image/jpeg"
                    },
                    content=image_data
                )
                
                if upload_response.status_code in [200, 201]:
                    uploaded_assets.append({
                        "status": "READY",
                        "description": {"text": content[:200]},
                        "media": asset,
                        "title": {"text": "Image"}
                    })
                    print(f"✅ Image uploaded: {asset}")
            
            except Exception as e:
                print(f"❌ Failed to upload image: {e}")
                continue
        
        return uploaded_assets