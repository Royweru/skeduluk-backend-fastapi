# app/services/platforms/youtube.py
"""
YouTube platform service for video uploads.
‚úÖ REAL FIX: Uses Google's official API client library
"""

from typing import Dict, List, Any, Optional
from .base_platform import BasePlatformService
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from google.oauth2.credentials import Credentials
import sys


class YouTubeService(BasePlatformService):
    """YouTube platform service implementation"""
    
    PLATFORM_NAME = "YOUTUBE"
    MAX_IMAGES = 0
    MAX_VIDEOS = 1
    MAX_VIDEO_SIZE_MB = 128 * 1024
    MAX_VIDEO_DURATION_SECONDS = 3600
    
    @classmethod
    async def post(
        cls,
        access_token: str,
        content: str,
        image_urls: Optional[List[str]] = None,
        video_urls: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Upload video to YouTube using Google's official API client."""
        print(f"Ìæ¨ YouTube: Starting video upload")
        print(f"Ì¥ç DEBUG: Using Google API Client version")
        
        if not video_urls or len(video_urls) == 0:
            return cls.format_error_response("YouTube requires a video")
        
        error = cls.validate_media_count(image_urls, video_urls)
        if error:
            return cls.format_error_response(error)
        
        try:
            video_url = video_urls[0]
            print(f"Ìæ¨ YouTube: Downloading video from {video_url}")
            video_data = await cls.download_media(video_url, timeout=300)
            
            if not video_data:
                return cls.format_error_response("Failed to download video")
            
            video_size_mb = len(video_data) / (1024 * 1024)
            print(f"Ìæ¨ YouTube: Video size: {video_size_mb:.2f} MB")
            
            title = content[:100] if len(content) <= 100 else content[:97] + "..."
            description = content
            privacy_status = kwargs.get("privacy_status", "public")
            category_id = kwargs.get("category_id", "22")
            tags = kwargs.get("tags", [])
            
            credentials = Credentials(token=access_token)
            youtube = build('youtube', 'v3', credentials=credentials)
            
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "categoryId": category_id
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False
                }
            }
            
            if tags:
                body["snippet"]["tags"] = tags
            
            print(f"Ìæ¨ YouTube: Uploading video ({video_size_mb:.2f}MB)...")
            
            media = MediaInMemoryUpload(
                video_data,
                mimetype="video/mp4",
                resumable=True,
                chunksize=1024*1024
            )
            
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            
            response = None
            last_progress = 0
            
            while response is None:
                try:
                    status, response = request.next_chunk()
                    if status:
                        progress = int(status.progress() * 100)
                        if progress != last_progress:
                            print(f"   Ì≥§ Upload progress: {progress}%")
                            last_progress = progress
                except Exception as chunk_error:
                    print(f"‚ùå Upload chunk error: {chunk_error}")
                    return cls.format_error_response(f"Upload failed: {str(chunk_error)}")
            
            video_id = response.get("id")
            
            if not video_id:
                return cls.format_error_response("No video ID in response")
            
            print(f"‚úÖ YouTube: Video uploaded successfully!")
            print(f"   Video ID: {video_id}")
            
            return cls.format_success_response(
                video_id,
                f"https://www.youtube.com/watch?v={video_id}",
                video_id=video_id
            )
            
        except Exception as e:
            print(f"‚ùå YouTube upload error: {e}")
            import traceback
            traceback.print_exc()
            
            error_msg = str(e)
            
            if "quotaExceeded" in error_msg or "Daily Limit Exceeded" in error_msg:
                return cls.format_error_response("YouTube API quota exceeded. Try again tomorrow.")
            elif "has not been used" in error_msg or "is disabled" in error_msg:
                return cls.format_error_response(
                    "YouTube Data API v3 is not enabled. Enable it in Google Cloud Console: "
                    "https://console.cloud.google.com/apis/library/youtube.googleapis.com"
                )
            else:
                return cls.format_error_response(f"Upload failed: {error_msg}")
    
    @classmethod
    async def validate_token(cls, access_token: str) -> bool:
        """Validate YouTube/Google access token"""
        try:
            credentials = Credentials(token=access_token)
            youtube = build('youtube', 'v3', credentials=credentials)
            request = youtube.channels().list(part="snippet", mine=True)
            response = request.execute()
            return "items" in response and len(response["items"]) > 0
        except:
            return False
    
    @classmethod
    async def get_channel_info(cls, access_token: str) -> Optional[Dict[str, Any]]:
        """Get YouTube channel information"""
        try:
            credentials = Credentials(token=access_token)
            youtube = build('youtube', 'v3', credentials=credentials)
            
            request = youtube.channels().list(
                part="snippet,statistics",
                mine=True
            )
            response = request.execute()
            
            if response.get("items"):
                channel = response["items"][0]
                return {
                    "id": channel["id"],
                    "title": channel["snippet"]["title"],
                    "subscriber_count": channel["statistics"].get("subscriberCount", 0),
                    "video_count": channel["statistics"].get("videoCount", 0),
                    "thumbnail": channel["snippet"]["thumbnails"]["default"]["url"]
                }
            return None
        except:
            return None
