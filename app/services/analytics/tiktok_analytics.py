# app/services/analytics/tiktok_analytics.py
"""
TikTok analytics fetcher using TikTok API v2.
"""

from .base_analytics import BasePlatformService
import httpx
from typing import Dict, Any


class TikTokAnalyticsFetcher(BasePlatformService):
    """TikTok analytics implementation"""
    
    PLATFORM_NAME = "TIKTOK"
    API_BASE = "https://open.tiktokapis.com"
    
    async def fetch_post_metrics(
        self,
        access_token: str,
        platform_post_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch TikTok video analytics.
        Note: TikTok analytics require separate permissions.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get video info with metrics
                response = await client.post(
                    f"{self.API_BASE}/v2/video/query/",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "filters": {
                            "video_ids": [platform_post_id]
                        }
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("error", {}).get("code") != "ok":
                        return self.format_error_response(data.get("error", {}).get("message", "Unknown error"))
                    
                    videos = data.get("data", {}).get("videos", [])
                    if not videos:
                        return self.format_error_response("Video not found")
                    
                    video = videos[0]
                    
                    # TikTok provides these metrics
                    view_count = video.get("view_count", 0)
                    like_count = video.get("like_count", 0)
                    comment_count = video.get("comment_count", 0)
                    share_count = video.get("share_count", 0)
                    
                    return {
                        "views": view_count,
                        "impressions": view_count,  # TikTok uses views
                        "reach": view_count,
                        "likes": like_count,
                        "comments": comment_count,
                        "shares": share_count,
                        "saves": 0,  # Not available
                        "clicks": 0,
                        "platform_specific": {
                            "play_count": video.get("play_count", 0),
                            "duration": video.get("duration", 0)
                        }
                    }
                else:
                    return self.format_error_response(f"API error: {response.status_code}")
                    
        except Exception as e:
            return self.format_error_response(str(e))
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate TikTok token"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.API_BASE}/v2/user/info/",
                    params={"fields": "open_id,display_name"},
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("error", {}).get("code") == "ok"
                return False
        except:
            return False