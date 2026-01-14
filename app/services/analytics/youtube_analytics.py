# app/services/analytics/youtube_analytics.py
"""
YouTube analytics fetcher using YouTube Analytics API.
"""

from typing import Dict, Any
from .base_analytics import BaseAnalyticsFetcher
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


class YouTubeAnalyticsFetcher(BaseAnalyticsFetcher):
    """YouTube analytics implementation"""
    
    PLATFORM_NAME = "YOUTUBE"
    
    async def fetch_post_metrics(
        self,
        access_token: str,
        platform_post_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch YouTube video analytics.
        Uses YouTube Data API v3 for basic stats.
        """
        try:
            credentials = Credentials(token=access_token)
            youtube = build('youtube', 'v3', credentials=credentials)
            
            # Get video statistics
            request = youtube.videos().list(
                part="statistics,contentDetails",
                id=platform_post_id
            )
            response = request.execute()
            
            if not response.get('items'):
                return self.format_error_response("Video not found")
            
            video = response['items'][0]
            stats = video.get('statistics', {})
            
            view_count = int(stats.get('viewCount', 0))
            like_count = int(stats.get('likeCount', 0))
            comment_count = int(stats.get('commentCount', 0))
            
            return {
                "views": view_count,
                "impressions": view_count,
                "reach": view_count,
                "likes": like_count,
                "comments": comment_count,
                "shares": 0,  # Not available in API
                "saves": 0,
                "clicks": 0,
                "platform_specific": {
                    "favorite_count": int(stats.get('favoriteCount', 0)),
                    "duration": video.get('contentDetails', {}).get('duration', ''),
                    "definition": video.get('contentDetails', {}).get('definition', 'sd')
                }
            }
            
        except Exception as e:
            return self.format_error_response(str(e))
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate YouTube/Google token"""
        try:
            credentials = Credentials(token=access_token)
            youtube = build('youtube', 'v3', credentials=credentials)
            
            request = youtube.channels().list(part="snippet", mine=True)
            response = request.execute()
            return "items" in response and len(response["items"]) > 0
        except:
            return False