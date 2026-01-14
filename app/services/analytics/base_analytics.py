# app/services/analytics/base_analytics.py
"""
Base class for analytics fetching.
Each platform inherits from this.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseAnalyticsFetcher(ABC):
    """Abstract base for platform analytics"""
    
    PLATFORM_NAME: str = "UNKNOWN"
    
    @abstractmethod
    async def fetch_post_metrics(
        self,
        access_token: str,
        platform_post_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch analytics for a specific post.
        
        Returns standardized metrics:
        {
            "views": int,
            "impressions": int,
            "reach": int,
            "likes": int,
            "comments": int,
            "shares": int,
            "saves": int,
            "clicks": int,
            "platform_specific": {dict of platform-unique metrics}
        }
        """
        pass
    
    @abstractmethod
    async def validate_token(self, access_token: str) -> bool:
        """Validate if token has analytics permissions"""
        pass
    
    @classmethod
    def format_error_response(cls, error: str) -> Dict[str, Any]:
        """Standardized error format"""
        return {
            "success": False,
            "error": f"{cls.PLATFORM_NAME} analytics error: {error}"
        }