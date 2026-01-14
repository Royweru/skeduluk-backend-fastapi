# app/services/analytics/instagram_analytics.py
"""
Instagram analytics fetcher via Facebook Graph API.
"""

from .base_analytics import BaseAnalyticsFetcher
import httpx
from typing import Dict, Any, Optional


class InstagramAnalyticsFetcher(BaseAnalyticsFetcher):
    """Instagram analytics implementation"""
    
    PLATFORM_NAME = "INSTAGRAM"
    API_BASE = "https://graph.facebook.com/v20.0"
    
    async def fetch_post_metrics(
        self,
        access_token: str,
        platform_post_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch Instagram media insights.
        Works for both feed posts and reels.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get media insights
                response = await client.get(
                    f"{self.API_BASE}/{platform_post_id}/insights",
                    params={
                        "metric": "impressions,reach,likes,comments,shares,saved,engagement",
                        "access_token": access_token
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    insights = data.get("data", [])
                    
                    # Parse metrics into dict
                    metrics_dict = {
                        insight["name"]: insight["values"][0]["value"]
                        for insight in insights
                        if insight.get("values")
                    }
                    
                    # Also get basic post info
                    post_response = await client.get(
                        f"{self.API_BASE}/{platform_post_id}",
                        params={
                            "fields": "like_count,comments_count",
                            "access_token": access_token
                        }
                    )
                    
                    post_data = post_response.json() if post_response.status_code == 200 else {}
                    
                    impressions = metrics_dict.get("impressions", 0)
                    reach = metrics_dict.get("reach", 0)
                    
                    return {
                        "views": impressions,
                        "impressions": impressions,
                        "reach": reach,
                        "likes": post_data.get("like_count", metrics_dict.get("likes", 0)),
                        "comments": post_data.get("comments_count", metrics_dict.get("comments", 0)),
                        "shares": metrics_dict.get("shares", 0),
                        "saves": metrics_dict.get("saved", 0),
                        "clicks": 0,
                        "platform_specific": {
                            "engagement": metrics_dict.get("engagement", 0),
                            "profile_visits": 0  # Requires account-level insights
                        }
                    }
                else:
                    return self.format_error_response(f"API error: {response.status_code}")
                    
        except Exception as e:
            return self.format_error_response(str(e))
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate Instagram/Facebook token"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.API_BASE}/me",
                    params={"access_token": access_token}
                )
                return response.status_code == 200
        except:
            return False