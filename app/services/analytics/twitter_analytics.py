# app/services/analytics/twitter_analytics.py
from .base_analytics import BaseAnalyticsFetcher
import httpx
from typing import Dict, Any


class TwitterAnalyticsFetcher(BaseAnalyticsFetcher):
    """Twitter/X analytics implementation"""
    
    PLATFORM_NAME = "TWITTER"
    API_BASE = "https://api.twitter.com/2"
    
    async def fetch_post_metrics(
        self,
        access_token: str,
        platform_post_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch Twitter post metrics.
        Uses OAuth 1.0a tokens (format: "token:secret")
        """
        try:
            if ':' not in access_token:
                return self.format_error_response("Invalid token format")
            
            from requests_oauthlib import OAuth1Session
            from app.config import settings
            
            oauth_token, oauth_token_secret = access_token.split(':', 1)
            
            twitter = OAuth1Session(
                client_key=settings.TWITTER_API_KEY,
                client_secret=settings.TWITTER_API_SECRET,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret
            )
            
            # Fetch tweet with public metrics
            response = twitter.get(
                f"{self.API_BASE}/tweets/{platform_post_id}",
                params={
                    "tweet.fields": "public_metrics,created_at",
                    "expansions": "author_id"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                metrics = data.get("data", {}).get("public_metrics", {})
                
                return {
                    "views": metrics.get("impression_count", 0),
                    "impressions": metrics.get("impression_count", 0),
                    "reach": metrics.get("impression_count", 0),  # Twitter doesn't separate reach
                    "likes": metrics.get("like_count", 0),
                    "comments": metrics.get("reply_count", 0),
                    "shares": metrics.get("retweet_count", 0),
                    "saves": metrics.get("bookmark_count", 0),
                    "clicks": 0,  # Not available in basic endpoint
                    "platform_specific": {
                        "quote_count": metrics.get("quote_count", 0),
                        "url_link_clicks": 0,  # Requires elevated access
                        "user_profile_clicks": 0
                    }
                }
            else:
                return self.format_error_response(f"API error: {response.status_code}")
                
        except Exception as e:
            return self.format_error_response(str(e))
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate Twitter token"""
        try:
            if ':' not in access_token:
                return False
            
            from requests_oauthlib import OAuth1Session
            from app.config import settings
            
            oauth_token, oauth_token_secret = access_token.split(':', 1)
            
            twitter = OAuth1Session(
                client_key=settings.TWITTER_API_KEY,
                client_secret=settings.TWITTER_API_SECRET,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret
            )
            
            response = twitter.get(f"{self.API_BASE}/users/me", timeout=10)
            return response.status_code == 200
        except:
            return False