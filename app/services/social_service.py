# app/services/social_service.py
import httpx
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, crud
from ..config import settings

class SocialService:
    @staticmethod
    async def publish_to_platform(
        connection: models.SocialConnection,
        content: str,
        image_urls: List[str] = None
    ) -> Dict[str, Any]:
        """Publish content to a specific social platform"""
        if connection.platform == "TWITTER":
            return await SocialService._post_to_twitter(connection, content, image_urls)
        elif connection.platform == "FACEBOOK":
            return await SocialService._post_to_facebook(connection, content, image_urls)
        elif connection.platform == "LINKEDIN":
            return await SocialService._post_to_linkedin(connection, content, image_urls)
        else:
            return {"success": False, "error": f"Unsupported platform: {connection.platform}"}
    
    @staticmethod
    async def _post_to_twitter(
        connection: models.SocialConnection,
        content: str,
        image_urls: List[str] = None
    ) -> Dict[str, Any]:
        """Post to Twitter/X"""
        headers = {
            "Authorization": f"Bearer {connection.access_token}",
            "Content-Type": "application/json"
        }
        
        # Prepare tweet data
        tweet_data = {"text": content}
        
        # Handle media if provided
        media_ids = []
        if image_urls:
            # First upload media
            for image_url in image_urls:
                media_response = await SocialService._upload_twitter_media(
                    connection.access_token, image_url
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
    async def _upload_twitter_media(access_token: str, image_url: str) -> Dict[str, Any]:
        """Upload media to Twitter"""
        # Download image first
        async with httpx.AsyncClient() as client:
            image_response = await client.get(image_url)
            if image_response.status_code != 200:
                return {"error": "Failed to download image"}
            
            image_data = image_response.content
        
        # Upload to Twitter
        headers = {"Authorization": f"Bearer {access_token}"}
        files = {"media": image_data}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                headers=headers,
                files=files
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Media upload failed: {response.text}"}
    
    @staticmethod
    async def _post_to_facebook(
        connection: models.SocialConnection,
        content: str,
        image_urls: List[str] = None
    ) -> Dict[str, Any]:
        """Post to Facebook"""
        # Get user's pages (for posting)
        pages_url = f"https://graph.facebook.com/me/accounts?access_token={connection.access_token}"
        
        async with httpx.AsyncClient() as client:
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
            
            # Handle media if provided
            if image_urls:
                # For simplicity, we'll use the first image
                post_data["url"] = image_urls[0]
                post_url = f"https://graph.facebook.com/{page_id}/photos"
            else:
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
        image_urls: List[str] = None
    ) -> Dict[str, Any]:
        """Post to LinkedIn"""
        # Get user profile
        profile_url = "https://api.linkedin.com/v2/people/~:(id)"
        headers = {"Authorization": f"Bearer {connection.access_token}"}
        
        async with httpx.AsyncClient() as client:
            profile_response = await client.get(profile_url, headers=headers)
            
            if profile_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to get LinkedIn profile: {profile_response.text}"
                }
            
            profile_data = profile_response.json()
            person_id = profile_data["id"]
            
            # Prepare post data
            post_data = {
                "author": f"urn:li:person:{person_id}",
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
            
            # Handle media if provided
            if image_urls:
                # Register image first
                register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
                register_data = {
                    "registerUploadRequest": {
                        "owner": f"urn:li:person:{person_id}",
                        "serviceRelationships": [
                            {
                                "relationshipType": "OWNER",
                                "identifier": "urn:li:digitalmediaAsset:C5522"
                            }
                        ],
                        "recipes": [
                            "urn:li:digitalmediaRecipe:feedshare-image"
                        ]
                    }
                }
                
                register_response = await client.post(
                    register_url,
                    headers=headers,
                    json=register_data
                )
                
                if register_response.status_code == 200:
                    register_result = register_response.json()
                    upload_url = register_result["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.UploadUrl"]
                    asset = register_result["value"]["asset"]
                    
                    # Upload image
                    image_response = await client.get(image_urls[0])
                    if image_response.status_code == 200:
                        upload_response = await client.put(
                            upload_url,
                            headers={"Authorization": f"Bearer {connection.access_token}"},
                            content=image_response.content
                        )
                        
                        if upload_response.status_code == 201:
                            # Update post data with media
                            post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
                            post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                                {
                                    "status": "READY",
                                    "description": {
                                        "text": content
                                    },
                                    "media": asset,
                                    "title": {
                                        "text": "Image"
                                    }
                                }
                            ]
            
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