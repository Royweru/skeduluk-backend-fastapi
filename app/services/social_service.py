# app/services/social_service.py
import httpx
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import os
from pathlib import Path

from .. import models, crud
from ..config import settings

class SocialService:
    @staticmethod
    async def publish_to_platform(
        connection: models.SocialConnection,
        content: str,
        image_urls: List[str] = None,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
        """Publish content to a specific social platform"""
        platform = connection.platform.upper()
        
        if platform == "TWITTER":
            return await SocialService._post_to_twitter(connection, content, image_urls, video_urls)
        elif platform == "FACEBOOK":
            return await SocialService._post_to_facebook(connection, content, image_urls, video_urls)
        elif platform == "LINKEDIN":
            return await SocialService._post_to_linkedin(connection, content, image_urls, video_urls)
        elif platform == "INSTAGRAM":
            return await SocialService._post_to_instagram(connection, content, image_urls, video_urls)
        elif platform == "TIKTOK":
            return await SocialService._post_to_tiktok(connection, content, video_urls)
        elif platform == "YOUTUBE":
            return await SocialService._post_to_youtube(connection, content, video_urls)
        else:
            return {"success": False, "error": f"Unsupported platform: {connection.platform}"}
    
    @staticmethod
    async def _get_media_file(url: str) -> Optional[bytes]:
        """Download media file from URL"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.content
                return None
        except Exception as e:
            print(f"Error downloading media: {e}")
            return None
    
    @staticmethod
    async def _post_to_twitter(
        connection: models.SocialConnection,
        content: str,
        image_urls: List[str] = None,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
        """
        Post to Twitter/X
        Note: Twitter allows either 1 video OR up to 4 images per tweet, not both
        """
        headers = {
            "Authorization": f"Bearer {connection.access_token}",
            "Content-Type": "application/json"
        }
        
        # Prepare tweet data
        tweet_data = {"text": content}
        
        media_ids = []
        
        # Handle video (priority over images if both provided)
        if video_urls:
            # Twitter allows only 1 video per tweet
            video_url = video_urls[0]
            video_response = await SocialService._upload_twitter_video(
                connection.access_token, video_url
            )
            if video_response.get("media_id_string"):
                media_ids.append(video_response["media_id_string"])
        
        # Handle images (only if no video)
        elif image_urls:
            # Twitter allows up to 4 images
            for image_url in image_urls[:4]:
                media_response = await SocialService._upload_twitter_media(
                    connection.access_token, image_url, media_type="image"
                )
                if media_response.get("media_id_string"):
                    media_ids.append(media_response["media_id_string"])
        
        if media_ids:
            tweet_data["media"] = {"media_ids": media_ids}
        
        # Post tweet
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.twitter.com/2/tweets",
                headers=headers,
                json=tweet_data
            )
            
            if response.status_code == 201:
                data = response.json()
                return {
                    "success": True,
                    "platform_post_id": data["data"]["id"]
                }
            else:
                return {
                    "success": False,
                    "error": f"Twitter API error: {response.text}"
                }
    
    @staticmethod
    async def _upload_twitter_media(
        access_token: str, 
        media_url: str, 
        media_type: str = "image"
    ) -> Dict[str, Any]:
        """Upload media (image or video) to Twitter"""
        # Download media first
        media_data = await SocialService._get_media_file(media_url)
        if not media_data:
            return {"error": "Failed to download media"}
        
        # Upload to Twitter
        headers = {"Authorization": f"Bearer {access_token}"}
        files = {"media": media_data}
        
        # Determine media category
        media_category = "tweet_image" if media_type == "image" else "tweet_video"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                headers=headers,
                files=files,
                data={"media_category": media_category}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Media upload failed: {response.text}"}
    
    @staticmethod
    async def _upload_twitter_video(access_token: str, video_url: str) -> Dict[str, Any]:
        """
        Upload video to Twitter using chunked upload
        Twitter requires INIT -> APPEND -> FINALIZE process for videos
        """
        video_data = await SocialService._get_media_file(video_url)
        if not video_data:
            return {"error": "Failed to download video"}
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient(timeout=120.0) as client:
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
                return {"error": f"Video init failed: {init_response.text}"}
            
            media_id = init_response.json()["media_id_string"]
            
            # APPEND (chunked)
            chunk_size = 5 * 1024 * 1024  # 5MB chunks
            for i in range(0, len(video_data), chunk_size):
                chunk = video_data[i:i + chunk_size]
                segment_index = i // chunk_size
                
                append_response = await client.post(
                    "https://upload.twitter.com/1.1/media/upload.json",
                    headers=headers,
                    data={
                        "command": "APPEND",
                        "media_id": media_id,
                        "segment_index": segment_index
                    },
                    files={"media": chunk}
                )
                
                if append_response.status_code != 204:
                    return {"error": f"Video append failed: {append_response.text}"}
            
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
                return finalize_response.json()
            else:
                return {"error": f"Video finalize failed: {finalize_response.text}"}
    
    @staticmethod
    async def _post_to_facebook(
        connection: models.SocialConnection,
        content: str,
        image_urls: List[str] = None,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
        """Post to Facebook (supports images and videos)"""
        # Get user's pages (for posting)
        pages_url = f"https://graph.facebook.com/me/accounts?access_token={connection.access_token}"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            pages_response = await client.get(pages_url)
            
            if pages_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to get Facebook pages: {pages_response.text}"
                }
            
            pages_data = pages_response.json()
            if not pages_data.get("data"):
                return {
                    "success": False,
                    "error": "No Facebook pages found"
                }
            
            # Use the first page
            page = pages_data["data"][0]
            page_access_token = page["access_token"]
            page_id = page["id"]
            
            # Prepare post data
            post_data = {
                "message": content,
                "access_token": page_access_token
            }
            
            # Handle video (priority over images)
            if video_urls:
                # Facebook allows 1 video per post
                video_url = video_urls[0]
                video_data = await SocialService._get_media_file(video_url)
                
                if video_data:
                    post_url = f"https://graph-video.facebook.com/{page_id}/videos"
                    files = {"source": ("video.mp4", video_data, "video/mp4")}
                    
                    video_response = await client.post(
                        post_url,
                        data=post_data,
                        files=files
                    )
                    
                    if video_response.status_code == 200:
                        result = video_response.json()
                        return {
                            "success": True,
                            "platform_post_id": result.get("id")
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Facebook video upload error: {video_response.text}"
                        }
            
            # Handle images (only if no video)
            elif image_urls:
                # For single image
                if len(image_urls) == 1:
                    post_data["url"] = image_urls[0]
                    post_url = f"https://graph.facebook.com/{page_id}/photos"
                else:
                    # For multiple images, need to create album first
                    # For simplicity, using first image
                    post_data["url"] = image_urls[0]
                    post_url = f"https://graph.facebook.com/{page_id}/photos"
            else:
                # Text-only post
                post_url = f"https://graph.facebook.com/{page_id}/feed"
            
            # Post to Facebook
            post_response = await client.post(post_url, data=post_data)
            
            if post_response.status_code == 200:
                post_result = post_response.json()
                return {
                    "success": True,
                    "platform_post_id": post_result.get("id") or post_result.get("post_id")
                }
            else:
                return {
                    "success": False,
                    "error": f"Facebook API error: {post_response.text}"
                }
    
    @staticmethod
    async def _post_to_linkedin(
        connection: models.SocialConnection,
        content: str,
        image_urls: List[str] = None,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
        """Post to LinkedIn (supports images and videos)"""
        headers = {
            "Authorization": f"Bearer {connection.access_token}",
            "Content-Type": "application/json"
        }
        
        # Get user profile
        profile_url = "https://api.linkedin.com/v2/userinfo"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            profile_response = await client.get(profile_url, headers=headers)
            
            if profile_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to get LinkedIn profile: {profile_response.text}"
                }
            
            profile_data = profile_response.json()
            person_id = profile_data["sub"]
            person_urn = f"urn:li:person:{person_id}"
            
            # Prepare base post data
            post_data = {
                "author": person_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": content
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            # Handle video (priority over images)
            if video_urls:
                video_url = video_urls[0]
                video_asset = await SocialService._upload_linkedin_video(
                    connection.access_token, person_urn, video_url
                )
                
                if video_asset:
                    post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "VIDEO"
                    post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                        {
                            "status": "READY",
                            "description": {
                                "text": content
                            },
                            "media": video_asset,
                            "title": {
                                "text": "Video"
                            }
                        }
                    ]
            
            # Handle images (only if no video)
            elif image_urls:
                image_assets = []
                
                for image_url in image_urls[:9]:  # LinkedIn allows up to 9 images
                    image_asset = await SocialService._upload_linkedin_image(
                        connection.access_token, person_urn, image_url
                    )
                    if image_asset:
                        image_assets.append({
                            "status": "READY",
                            "description": {
                                "text": content
                            },
                            "media": image_asset,
                            "title": {
                                "text": "Image"
                            }
                        })
                
                if image_assets:
                    post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
                    post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = image_assets
            
            # Post to LinkedIn
            post_url = "https://api.linkedin.com/v2/ugcPosts"
            post_response = await client.post(post_url, headers=headers, json=post_data)
            
            if post_response.status_code == 201:
                post_result = post_response.json()
                return {
                    "success": True,
                    "platform_post_id": post_result["id"]
                }
            else:
                return {
                    "success": False,
                    "error": f"LinkedIn API error: {post_response.text}"
                }
    
    @staticmethod
    async def _upload_linkedin_image(
        access_token: str,
        person_urn: str,
        image_url: str
    ) -> Optional[str]:
        """Upload image to LinkedIn and return asset URN"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Register upload
            register_data = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": person_urn,
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }
                    ]
                }
            }
            
            register_response = await client.post(
                "https://api.linkedin.com/v2/assets?action=registerUpload",
                headers=headers,
                json=register_data
            )
            
            if register_response.status_code != 200:
                print(f"LinkedIn image register failed: {register_response.text}")
                return None
            
            register_result = register_response.json()
            upload_url = register_result["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
            asset_urn = register_result["value"]["asset"]
            
            # Download image
            image_data = await SocialService._get_media_file(image_url)
            if not image_data:
                return None
            
            # Upload image
            upload_headers = {"Authorization": f"Bearer {access_token}"}
            upload_response = await client.put(
                upload_url,
                headers=upload_headers,
                content=image_data
            )
            
            if upload_response.status_code == 201:
                return asset_urn
            else:
                print(f"LinkedIn image upload failed: {upload_response.text}")
                return None
    
    @staticmethod
    async def _upload_linkedin_video(
        access_token: str,
        person_urn: str,
        video_url: str
    ) -> Optional[str]:
        """Upload video to LinkedIn and return asset URN"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Register upload
            register_data = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
                    "owner": person_urn,
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }
                    ]
                }
            }
            
            register_response = await client.post(
                "https://api.linkedin.com/v2/assets?action=registerUpload",
                headers=headers,
                json=register_data
            )
            
            if register_response.status_code != 200:
                print(f"LinkedIn video register failed: {register_response.text}")
                return None
            
            register_result = register_response.json()
            upload_url = register_result["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
            asset_urn = register_result["value"]["asset"]
            
            # Download video
            video_data = await SocialService._get_media_file(video_url)
            if not video_data:
                return None
            
            # Upload video
            upload_headers = {"Authorization": f"Bearer {access_token}"}
            upload_response = await client.put(
                upload_url,
                headers=upload_headers,
                content=video_data
            )
            
            if upload_response.status_code == 201:
                return asset_urn
            else:
                print(f"LinkedIn video upload failed: {upload_response.text}")
                return None
    
    @staticmethod
    async def _post_to_instagram(
        connection: models.SocialConnection,
        content: str,
        image_urls: List[str] = None,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
        """
        Post to Instagram (via Facebook Graph API)
        Note: Instagram posting requires Instagram Business Account connected to Facebook Page
        """
        # Instagram Graph API requires Facebook access token
        headers = {"Authorization": f"Bearer {connection.access_token}"}
        
        async with httpx.AsyncClient(timeout=90.0) as client:
            # Get Instagram Business Account ID
            ig_account_url = f"https://graph.facebook.com/v18.0/me/accounts?access_token={connection.access_token}"
            
            accounts_response = await client.get(ig_account_url)
            if accounts_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to get Instagram account: {accounts_response.text}"
                }
            
            accounts_data = accounts_response.json()
            if not accounts_data.get("data"):
                return {
                    "success": False,
                    "error": "No Facebook pages with Instagram connected"
                }
            
            # Get Instagram account from first page
            page = accounts_data["data"][0]
            page_id = page["id"]
            page_token = page["access_token"]
            
            # Get Instagram Business Account ID
            ig_url = f"https://graph.facebook.com/v18.0/{page_id}?fields=instagram_business_account&access_token={page_token}"
            ig_response = await client.get(ig_url)
            
            if ig_response.status_code != 200:
                return {
                    "success": False,
                    "error": "Instagram Business Account not found"
                }
            
            ig_data = ig_response.json()
            ig_account_id = ig_data.get("instagram_business_account", {}).get("id")
            
            if not ig_account_id:
                return {
                    "success": False,
                    "error": "Instagram Business Account not connected to this page"
                }
            
            # Create media container
            container_data = {
                "caption": content,
                "access_token": page_token
            }
            
            # Handle video or image
            if video_urls:
                # Instagram Reels
                container_data["media_type"] = "REELS"
                container_data["video_url"] = video_urls[0]
            elif image_urls:
                container_data["image_url"] = image_urls[0]
            else:
                return {
                    "success": False,
                    "error": "Instagram requires at least one image or video"
                }
            
            # Create container
            container_url = f"https://graph.facebook.com/v18.0/{ig_account_id}/media"
            container_response = await client.post(container_url, data=container_data)
            
            if container_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to create Instagram container: {container_response.text}"
                }
            
            container_id = container_response.json()["id"]
            
            # Publish container
            publish_data = {
                "creation_id": container_id,
                "access_token": page_token
            }
            
            publish_url = f"https://graph.facebook.com/v18.0/{ig_account_id}/media_publish"
            publish_response = await client.post(publish_url, data=publish_data)
            
            if publish_response.status_code == 200:
                result = publish_response.json()
                return {
                    "success": True,
                    "platform_post_id": result["id"]
                }
            else:
                return {
                    "success": False,
                    "error": f"Instagram publish error: {publish_response.text}"
                }
    
    @staticmethod
    async def _post_to_tiktok(
        connection: models.SocialConnection,
        content: str,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
        """
        Post to TikTok
        Note: TikTok requires video content
        """
        if not video_urls:
            return {
                "success": False,
                "error": "TikTok requires a video"
            }
        
        # TikTok API implementation
        # Note: This is a simplified version. Actual implementation requires:
        # 1. TikTok Content Posting API access
        # 2. Video upload to TikTok's servers
        # 3. Handling TikTok's specific requirements
        
        return {
            "success": False,
            "error": "TikTok posting coming soon"
        }
    
    @staticmethod
    async def _post_to_youtube(
        connection: models.SocialConnection,
        content: str,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
        """
        Post to YouTube
        Note: YouTube requires video content
        """
        if not video_urls:
            return {
                "success": False,
                "error": "YouTube requires a video"
            }
        
        # YouTube API implementation
        # Note: This requires YouTube Data API v3
        
        return {
            "success": False,
            "error": "YouTube posting coming soon"
        }
class TwitterService:
    """Service for Twitter API v2 operations"""
    
    @staticmethod
    async def post_tweet(
        access_token: str,
        text: str,
        media_ids: Optional[list] = None,
        reply_to_tweet_id: Optional[str] = None,
        quote_tweet_id: Optional[str] = None
    ) -> Dict:
        """
        Post a tweet using Twitter API v2
        
        Args:
            access_token: OAuth 2.0 access token
            text: Tweet text (max 280 characters)
            media_ids: List of media IDs to attach
            reply_to_tweet_id: Tweet ID to reply to
            quote_tweet_id: Tweet ID to quote
        
        Returns:
            Dict with tweet data or error
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {"text": text}
                
                # Add media if provided
                if media_ids:
                    payload["media"] = {"media_ids": media_ids}
                
                # Add reply settings if replying
                if reply_to_tweet_id:
                    payload["reply"] = {"in_reply_to_tweet_id": reply_to_tweet_id}
                
                # Add quote tweet if quoting
                if quote_tweet_id:
                    payload["quote_tweet_id"] = quote_tweet_id
                
                response = await client.post(
                    "https://api.twitter.com/2/tweets",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 201:
                    return {
                        "success": True,
                        "data": response.json()
                    }
                else:
                    error_data = response.json()
                    return {
                        "success": False,
                        "error": error_data.get("detail", "Failed to post tweet"),
                        "status_code": response.status_code
                    }
                    
        except Exception as e:
            print(f"Error posting tweet: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def delete_tweet(access_token: str, tweet_id: str) -> Dict:
        """Delete a tweet"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"https://api.twitter.com/2/tweets/{tweet_id}",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    return {"success": True, "data": response.json()}
                else:
                    return {
                        "success": False,
                        "error": response.json().get("detail", "Failed to delete tweet")
                    }
                    
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def get_user_tweets(
        access_token: str,
        user_id: str,
        max_results: int = 10
    ) -> Dict:
        """Get user's recent tweets"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.twitter.com/2/users/{user_id}/tweets",
                    params={"max_results": max_results},
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    return {"success": True, "data": response.json()}
                else:
                    return {
                        "success": False,
                        "error": response.json().get("detail", "Failed to fetch tweets")
                    }
                    
        except Exception as e:
            return {"success": False, "error": str(e)}