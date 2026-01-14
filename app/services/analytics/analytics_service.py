# app/services/analytics/analytics_service.py

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app import models
from app.crud.analytics_crud import AnalyticsCRUD
from .twitter_analytics import TwitterAnalyticsFetcher
from .facebook_analytics import FacebookAnalyticsFetcher
from .instagram_analytics import InstagramAnalyticsFetcher
from .linkedin_analytics import LinkedInAnalyticsFetcher
from .tiktok_analytics import TikTokAnalyticsFetcher
from .youtube_analytics import YouTubeAnalyticsFetcher


class AnalyticsService:
    """
    Central analytics service.
    Handles fetching and storing analytics for all platforms.
    """
    
    # Platform fetcher mapping
    FETCHERS = {
        "TWITTER": TwitterAnalyticsFetcher(),
        "FACEBOOK": FacebookAnalyticsFetcher(),
        "INSTAGRAM": InstagramAnalyticsFetcher(),
        "LINKEDIN": LinkedInAnalyticsFetcher(),
        "TIKTOK": TikTokAnalyticsFetcher(),
        "YOUTUBE": YouTubeAnalyticsFetcher(),
    }
    
    @classmethod
    async def fetch_post_analytics(
        cls,
        db: AsyncSession,
        post_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Fetch analytics for a post across all platforms it was published to.
        
        Returns:
            {
                "post_id": int,
                "platforms": {
                    "TWITTER": {"success": bool, "metrics": {...}, "error": str},
                    "FACEBOOK": {...}
                },
                "fetched_at": str
            }
        """
        # Get post
        from app.crud.post_crud import PostCRUD
        post = await PostCRUD.get_post_by_id(db, post_id, user_id)
        
        if not post:
            return {
                "success": False,
                "error": "Post not found"
            }
        
        # Get post results (platform-specific IDs)
        from app.crud.post_crud import PostResultCRUD
        results = await PostResultCRUD.get_results_by_post(db, post_id)
        
        if not results:
            return {
                "success": False,
                "error": "No published results found for this post"
            }
        
        # Get user's social connections
        from app.crud.social_connection_crud import SocialConnectionCRUD
        
        platform_analytics = {}
        
        for result in results:
            if result.status != "posted" or not result.platform_post_id:
                continue
            
            platform = result.platform.upper()
            
            # Get connection for token
            connection = await SocialConnectionCRUD.get_connection_by_platform(
                db, user_id, platform
            )
            
            if not connection:
                platform_analytics[platform] = {
                    "success": False,
                    "error": "No active connection found"
                }
                continue
            
            # Get fetcher for platform
            fetcher = cls.FETCHERS.get(platform)
            if not fetcher:
                platform_analytics[platform] = {
                    "success": False,
                    "error": "Analytics not supported for this platform"
                }
                continue
            
            # Fetch metrics
            try:
                metrics = await fetcher.fetch_post_metrics(
                    access_token=connection.access_token,
                    platform_post_id=result.platform_post_id,
                    page_id=getattr(connection, 'facebook_page_id', None)
                )
                
                if metrics.get("success") is False:
                    # Error response
                    platform_analytics[platform] = metrics
                    
                    # Save error to DB
                    await AnalyticsCRUD.update_error(
                        db, post_id, platform, metrics.get("error", "Unknown error")
                    )
                else:
                    # Success - save to DB
                    await AnalyticsCRUD.create_or_update_analytics(
                        db, post_id, platform, metrics
                    )
                    
                    platform_analytics[platform] = {
                        "success": True,
                        "metrics": metrics
                    }
                    
            except Exception as e:
                error_msg = f"Exception fetching analytics: {str(e)}"
                platform_analytics[platform] = {
                    "success": False,
                    "error": error_msg
                }
                
                await AnalyticsCRUD.update_error(db, post_id, platform, error_msg)
        
        return {
            "success": True,
            "post_id": post_id,
            "platforms": platform_analytics,
            "fetched_at": datetime.utcnow().isoformat()
        }
    
    @classmethod
    async def get_user_dashboard_analytics(
        cls,
        db: AsyncSession,
        user_id: int,
        days: int = 30,
        platform: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive analytics dashboard for a user.
        
        Returns aggregated metrics, top posts, and trends.
        """
        from datetime import timedelta
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get summary
        summary = await AnalyticsCRUD.get_user_analytics_summary(
            db, user_id, start_date, end_date, platform
        )
        
        # Get top posts
        top_posts = await AnalyticsCRUD.get_top_performing_posts(
            db, user_id, limit=5, metric='engagement_rate'
        )
        
        # Get analytics over time
        analytics_over_time = await AnalyticsCRUD.get_analytics_over_time(
            db, user_id, days=days, platform=platform
        )
        
        return {
            "summary": summary,
            "top_posts": top_posts,
            "analytics_over_time": analytics_over_time,
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        }
    
    @classmethod
    async def get_platform_comparison(
        cls,
        db: AsyncSession,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Compare performance across all platforms.
        """
        from datetime import timedelta
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        summary = await AnalyticsCRUD.get_user_analytics_summary(
            db, user_id, start_date, end_date
        )
        
        platforms = summary.get("by_platform", {})
        
        # Calculate best performing platform
        best_platform = None
        best_engagement = 0
        
        for platform, metrics in platforms.items():
            if metrics["engagement_rate"] > best_engagement:
                best_engagement = metrics["engagement_rate"]
                best_platform = platform
        
        return {
            "platforms": platforms,
            "best_platform": best_platform,
            "best_engagement_rate": best_engagement,
            "total_posts": summary.get("total_posts", 0),
            "total_engagement": summary.get("total_engagement", 0)
        }