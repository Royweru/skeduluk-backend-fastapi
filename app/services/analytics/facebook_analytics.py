# app/services/analytics/facebook_analytics.py

from .base_analytics import BaseAnalyticsFetcher
import httpx
from typing import Dict, Any, Optional

class FacebookAnalyticsFetcher(BaseAnalyticsFetcher):
    """Facebook analytics implementation"""
    
    PLATFORM_NAME = "FACEBOOK"
    API_BASE = "https://graph.facebook.com/v20.0"
    
    async def fetch_post_metrics(
        self,
        access_token: str,
        platform_post_id: str,
        page_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch Facebook post insights.
        Requires Page ID for Page posts.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Fetch post insights
                response = await client.get(
                    f"{self.API_BASE}/{platform_post_id}",
                    params={
                        "fields": "insights.metric(post_impressions,post_engaged_users,post_reactions_like_total,post_comments,post_shares)",
                        "access_token": access_token
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    insights = data.get("insights", {}).get("data", [])
                    
                    # Parse metrics
                    metrics_dict = {
                        insight["name"]: insight["values"][0]["value"]
                        for insight in insights
                        if insight.get("values")
                    }
                    
                    impressions = metrics_dict.get("post_impressions", 0)
                    engaged_users = metrics_dict.get("post_engaged_users", 0)
                    
                    return {
                        "views": impressions,
                        "impressions": impressions,
                        "reach": engaged_users,
                        "likes": metrics_dict.get("post_reactions_like_total", 0),
                        "comments": metrics_dict.get("post_comments", 0),
                        "shares": metrics_dict.get("post_shares", 0),
                        "saves": 0,  # Not available
                        "clicks": 0,  # Requires additional endpoint
                        "platform_specific": {
                            "engaged_users": engaged_users,
                            "negative_feedback": 0
                        }
                    }
                else:
                    return self.format_error_response(f"API error: {response.status_code}")
                    
        except Exception as e:
            return self.format_error_response(str(e))
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate Facebook token"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.API_BASE}/me",
                    params={"access_token": access_token}
                )
                return response.status_code == 200
        except:
            return False