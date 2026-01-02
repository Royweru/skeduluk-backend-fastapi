# app/services/social_service.py
import httpx
import json
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import asyncio
import mimetypes
from pathlib import Path
from requests_oauthlib import OAuth1Session
import base64
from io import BytesIO

from .. import models, crud
from ..config import settings
from .oauth_service import OAuthService


class SocialService:
    """Enhanced social media posting service"""

    @staticmethod
    async def ensure_valid_token(connection: models.SocialConnection, db: AsyncSession) -> str:
        """Ensure token is valid, refresh if needed"""
        if connection.token_expires_at and connection.token_expires_at < datetime.utcnow():
            print(f"🔄 Token expired for {connection.platform}, refreshing...")
            result = await OAuthService.refresh_access_token(connection, db)
            if not result:
                raise Exception(
                    f"Failed to refresh token for {connection.platform}")
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
        elif platform == "LINKEDIN":
            return await SocialService._post_to_linkedin(access_token, content, image_urls, video_urls)
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

    # ==================== TWITTER/X (FIXED) ====================

    @staticmethod
    async def _post_to_twitter(
        access_token: str,
        content: str,
        image_urls: List[str] = None,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
        """
        Post to Twitter/X using OAuth 1.0a (NOT Bearer token)
        """
        try:
            # ✅ Parse OAuth 1.0a tokens
            # Format: "oauth_token:oauth_token_secret"
            if ':' not in access_token:
                return {
                    "success": False,
                    "error": "Invalid Twitter token format. Expected 'oauth_token:oauth_secret'"
                }

            oauth_token, oauth_token_secret = access_token.split(':', 1)

            print(
                f"🐦 Twitter OAuth 1.0a - Token length: {len(oauth_token)}, Secret length: {len(oauth_token_secret)}")

            # ✅ Create OAuth1Session (synchronous library, but we'll use it)
            twitter = OAuth1Session(
                client_key=settings.TWITTER_API_KEY,
                client_secret=settings.TWITTER_API_SECRET,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret
            )

            tweet_data = {"text": content}
            media_ids = []

            # Handle images
            if image_urls:
                for image_url in image_urls[:4]:  # Twitter max 4 images
                    media_id = await SocialService._upload_twitter_media_oauth1(
                        twitter, image_url
                    )
                    if media_id:
                        media_ids.append(media_id)

            if media_ids:
                tweet_data["media"] = {"media_ids": media_ids}

            # Post tweet using OAuth 1.0a
            print(f"🐦 Posting tweet with OAuth 1.0a...")
            response = twitter.post(
                "https://api.twitter.com/2/tweets",
                json=tweet_data
            )

            print(f"🐦 Twitter response status: {response.status_code}")

            if response.status_code == 201:
                data = response.json()
                tweet_id = data["data"]["id"]

                return {
                    "success": True,
                    "platform_post_id": tweet_id,
                    "url": f"https://twitter.com/user/status/{tweet_id}"
                }
            else:
                error_text = response.text
                print(
                    f"❌ Twitter post error: {response.status_code} {error_text}")
                return {
                    "success": False,
                    "error": f"Twitter API error: {error_text}"
                }

        except Exception as e:
            print(f"❌ Twitter post exception: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    @staticmethod
    async def _upload_twitter_media_oauth1(
        twitter_session: OAuth1Session,
        media_url: str
    ) -> Optional[str]:
        """Upload media to Twitter using OAuth 1.0a"""
        try:
            media_data = await SocialService._download_media(media_url)
            if not media_data:
                return None

            # Determine media type
            content_type = mimetypes.guess_type(media_url)[0] or "image/jpeg"

            # Upload using OAuth 1.0a
            files = {"media": ("image.jpg", BytesIO(media_data), content_type)}
            response = twitter_session.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                files=files
            )

            if response.status_code == 200:
                return response.json().get("media_id_string")
            else:
                print(f"❌ Twitter media upload failed: {response.text}")
                return None

        except Exception as e:
            print(f"❌ Twitter media upload error: {e}")
            return None

    # ==================== LINKEDIN (NEW) ====================

    @staticmethod
    async def _post_to_linkedin(
        access_token: str,
        content: str,
        image_urls: List[str] = None,
        video_urls: List[str] = None
    ) -> Dict[str, Any]:
        """
        Post to LinkedIn using API v2
        Based on your working TypeScript implementation
        """
        print("💼 Starting LinkedIn post")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Step 1: Get user profile
                print("💼 Fetching LinkedIn profile...")
                profile_response = await client.get(
                    "https://api.linkedin.com/v2/userinfo",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "X-Restli-Protocol-Version": "2.0.0"
                    }
                )

                if profile_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to fetch LinkedIn profile: {profile_response.status_code} - {profile_response.text}"
                    }

                profile = profile_response.json()
                author_id = f"urn:li:person:{profile['sub']}"
                print(f"💼 Profile fetched - Author: {author_id}")

                # Step 2: Prepare post data
                post_data = {
                    "author": author_id,
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

                # Step 3: Handle images if provided
                if image_urls and len(image_urls) > 0:
                    print(
                        f"💼 Uploading {len(image_urls)} images to LinkedIn...")
                    uploaded_assets = []

                    for image_url in image_urls:
                        try:
                            # Register upload
                            print(f"💼 Registering upload for: {image_url}")
                            register_response = await client.post(
                                "https://api.linkedin.com/v2/assets?action=registerUpload",
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

                            register_data = register_response.json()

                            if "value" not in register_data or "uploadMechanism" not in register_data["value"]:
                                print(
                                    f"❌ Failed to register upload: {register_data}")
                                continue

                            upload_url = register_data["value"]["uploadMechanism"][
                                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                            asset = register_data["value"]["asset"]

                            # Download image
                            print(f"💼 Fetching image from: {image_url}")
                            image_data = await SocialService._download_media(image_url)
                            if not image_data:
                                continue

                            # Upload to LinkedIn
                            print(f"💼 Uploading image to LinkedIn...")
                            upload_response = await client.post(
                                upload_url,
                                headers={
                                    "Authorization": f"Bearer {access_token}",
                                    "Content-Type": "image/jpeg"
                                },
                                content=image_data
                            )

                            if upload_response.status_code in [200, 201]:
                                print(f"✅ Image uploaded: {asset}")
                                uploaded_assets.append(asset)
                            else:
                                print(
                                    f"❌ Image upload failed: {upload_response.status_code}")

                        except Exception as img_error:
                            print(
                                f"❌ Failed to upload image {image_url}: {img_error}")
                            continue

                    # Add uploaded images to post
                    if uploaded_assets:
                        post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
                        post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                            {
                                "status": "READY",
                                "description": {"text": content[:200]},
                                "media": asset,
                                "title": {"text": "Image"}
                            }
                            for asset in uploaded_assets
                        ]
                        print(f"💼 Added {len(uploaded_assets)} images to post")

                # Step 4: Post to LinkedIn
                print("💼 Posting to LinkedIn...")
                response = await client.post(
                    "https://api.linkedin.com/v2/ugcPosts",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0"
                    },
                    json=post_data
                )

                print(f"💼 Response status: {response.status_code}")
                response_text = response.text
                print(f"💼 Response: {response_text}")

                if response.status_code in [200, 201]:
                    try:
                        result = response.json()
                        post_id = result.get("id", "")
                        print(f"✅ LinkedIn post created: {post_id}")
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
                    return {
                        "success": False,
                        "error": f"LinkedIn API error: {response.status_code} - {response_text}"
                    }

        except Exception as e:
            print(f"❌ LinkedIn post exception: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    # ==================== FACEBOOK ====================

    @staticmethod
    async def _post_to_facebook_with_connection(
        connection: models.SocialConnection,
        content: str,
        image_urls: List[str] = None,
        video_urls: List[str] = None,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """Post to Facebook using selected page from database"""
        try:
            # ✅ Check if user has selected a page
            if not connection.facebook_page_id or not connection.facebook_page_access_token:
                return {
                    "success": False,
                    "error": "No Facebook Page selected. Please select a page in Settings."
                }
            
            page_id = connection.facebook_page_id
            page_token = connection.facebook_page_access_token
            page_name = connection.facebook_page_name
            
            print(f"📘 Posting to Facebook Page: {page_name} (ID: {page_id})")
            
            async with httpx.AsyncClient(timeout=90.0) as client:
                # Handle video posts
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
                                "url": f"https://www.facebook.com/{page_id}/posts/{post_id}"
                            }
                        else:
                            return {
                                "success": False,
                                "error": f"Video upload failed: {response.text}"
                            }

                # Handle images or text posts
                post_data = {
                    "message": content,
                    "access_token": page_token
                }

                if image_urls and len(image_urls) > 0:
                    # Post with image
                    post_data["url"] = image_urls[0]
                    post_url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
                else:
                    # Text-only post
                    post_url = f"https://graph.facebook.com/v20.0/{page_id}/feed"

                response = await client.post(post_url, data=post_data)

                if response.status_code == 200:
                    result = response.json()
                    post_id = result.get("id") or result.get("post_id")
                    
                    return {
                        "success": True,
                        "platform_post_id": post_id,
                        "url": f"https://www.facebook.com/{page_name}/posts/{post_id.split('_')[1] if '_' in post_id else post_id}"
                    }
                else:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", response.text)
                    return {
                        "success": False,
                        "error": f"Facebook post failed: {error_msg}"
                    }

        except Exception as e:
            print(f"❌ Facebook post error: {e}")
            import traceback
            traceback.print_exc()
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
                ig_account_id = ig_data.get(
                    "instagram_business_account", {}).get("id")

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
