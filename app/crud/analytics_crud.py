# app/crud/analytics_crud.py
"""
CRUD operations for analytics.
Keeps database operations separate from business logic.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload

from app import models


class AnalyticsCRUD:
    """Analytics database operations"""

    @staticmethod
    async def create_or_update_analytics(
        db: AsyncSession,
        post_id: int,
        platform: str,
        metrics: Dict[str, Any]
    ) -> models.PostAnalytics:
        """
        Create or update analytics for a post on a specific platform.
        Uses upsert pattern.
        """
        # Try to find existing analytics
        result = await db.execute(
            select(models.PostAnalytics).where(
                and_(
                    models.PostAnalytics.post_id == post_id,
                    models.PostAnalytics.platform == platform
                )
            )
        )
        analytics = result.scalar_one_or_none()

        # Calculate engagement rate
        engagement = metrics.get(
            'likes', 0) + metrics.get('comments', 0) + metrics.get('shares', 0)
        impressions = metrics.get(
            'impressions', 0) or metrics.get('views', 0) or 1
        engagement_rate = (engagement / impressions *
                           100) if impressions > 0 else 0.0

        if analytics:
            # Update existing
            analytics.views = metrics.get('views', 0)
            analytics.impressions = metrics.get('impressions', 0)
            analytics.reach = metrics.get('reach', 0)
            analytics.likes = metrics.get('likes', 0)
            analytics.comments = metrics.get('comments', 0)
            analytics.shares = metrics.get('shares', 0)
            analytics.saves = metrics.get('saves', 0)
            analytics.clicks = metrics.get('clicks', 0)
            analytics.engagement_rate = engagement_rate
            analytics.platform_specific_metrics = metrics.get(
                'platform_specific', {})
            analytics.fetched_at = datetime.utcnow()
            analytics.error = None
        else:
            # Create new
            analytics = models.PostAnalytics(
                post_id=post_id,
                platform=platform,
                views=metrics.get('views', 0),
                impressions=metrics.get('impressions', 0),
                reach=metrics.get('reach', 0),
                likes=metrics.get('likes', 0),
                comments=metrics.get('comments', 0),
                shares=metrics.get('shares', 0),
                saves=metrics.get('saves', 0),
                clicks=metrics.get('clicks', 0),
                engagement_rate=engagement_rate,
                platform_specific_metrics=metrics.get('platform_specific', {}),
                fetched_at=datetime.utcnow()
            )
            db.add(analytics)

        await db.commit()
        await db.refresh(analytics)
        return analytics

    @staticmethod
    async def update_error(
        db: AsyncSession,
        post_id: int,
        platform: str,
        error_message: str
    ) -> Optional[models.PostAnalytics]:
        """Record an error when fetching analytics fails"""
        result = await db.execute(
            select(models.PostAnalytics).where(
                and_(
                    models.PostAnalytics.post_id == post_id,
                    models.PostAnalytics.platform == platform
                )
            )
        )
        analytics = result.scalar_one_or_none()

        if analytics:
            analytics.error = error_message
            analytics.fetched_at = datetime.utcnow()
            await db.commit()
            await db.refresh(analytics)
            return analytics
        return None

    @staticmethod
    async def get_post_analytics(
        db: AsyncSession,
        post_id: int,
        platform: Optional[str] = None
    ) -> List[models.PostAnalytics]:
        """Get analytics for a specific post"""
        query = select(models.PostAnalytics).where(
            models.PostAnalytics.post_id == post_id
        )

        if platform:
            query = query.where(models.PostAnalytics.platform == platform)

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_user_analytics_summary(
        db: AsyncSession,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        platform: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated analytics summary for a user.
        Returns totals across all their posts.
        """
        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Build query for posts in date range
        posts_query = select(models.Post.id).where(
            and_(
                models.Post.user_id == user_id,
                models.Post.created_at >= start_date,
                models.Post.created_at <= end_date,
                models.Post.status.in_(['posted', 'partial'])
            )
        )

        posts_result = await db.execute(posts_query)
        post_ids = [p[0] for p in posts_result.all()]

        if not post_ids:
            return {
                "total_posts": 0,
                "total_views": 0,
                "total_impressions": 0,
                "total_likes": 0,
                "total_comments": 0,
                "total_shares": 0,
                "total_engagement": 0,
                "avg_engagement_rate": 0.0,
                "by_platform": {},
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }

        # Get analytics for these posts
        analytics_query = select(models.PostAnalytics).where(
            models.PostAnalytics.post_id.in_(post_ids)
        )

        if platform:
            analytics_query = analytics_query.where(
                models.PostAnalytics.platform == platform
            )

        analytics_result = await db.execute(analytics_query)
        analytics_list = analytics_result.scalars().all()

        # Aggregate metrics
        total_views = sum(a.views for a in analytics_list)
        total_impressions = sum(a.impressions for a in analytics_list)
        total_likes = sum(a.likes for a in analytics_list)
        total_comments = sum(a.comments for a in analytics_list)
        total_shares = sum(a.shares for a in analytics_list)
        total_engagement = total_likes + total_comments + total_shares

        avg_engagement_rate = (
            sum(a.engagement_rate for a in analytics_list) / len(analytics_list)
            if analytics_list else 0.0
        )

        # Platform breakdown
        by_platform = {}
        for analytics in analytics_list:
            plat = analytics.platform
            if plat not in by_platform:
                by_platform[plat] = {
                    "posts": 0,
                    "views": 0,
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                    "engagement_rate": 0.0
                }

            by_platform[plat]["posts"] += 1
            by_platform[plat]["views"] += analytics.views
            by_platform[plat]["likes"] += analytics.likes
            by_platform[plat]["comments"] += analytics.comments
            by_platform[plat]["shares"] += analytics.shares
            by_platform[plat]["engagement_rate"] += analytics.engagement_rate

        # Calculate averages for each platform
        for plat in by_platform:
            count = by_platform[plat]["posts"]
            by_platform[plat]["engagement_rate"] /= count if count > 0 else 1

        return {
            "total_posts": len(post_ids),
            "total_views": total_views,
            "total_impressions": total_impressions,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_shares": total_shares,
            "total_engagement": total_engagement,
            "avg_engagement_rate": avg_engagement_rate,
            "by_platform": by_platform,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }

    @staticmethod
    async def get_top_performing_posts(
        db: AsyncSession,
        user_id: int,
        limit: int = 10,
        metric: str = 'engagement_rate'
    ) -> List[Dict[str, Any]]:
        """Get top performing posts by a specific metric"""
        # Get user's posts with analytics
        query = (
            select(models.Post, models.PostAnalytics)
            .join(models.PostAnalytics)
            .where(models.Post.user_id == user_id)
        )

        # Order by metric
        if metric == 'engagement_rate':
            query = query.order_by(desc(models.PostAnalytics.engagement_rate))
        elif metric == 'views':
            query = query.order_by(desc(models.PostAnalytics.views))
        elif metric == 'likes':
            query = query.order_by(desc(models.PostAnalytics.likes))

        query = query.limit(limit)

        result = await db.execute(query)
        rows = result.all()

        return [
            {
                "post_id": post.id,
                "content": post.original_content[:100] + "..." if len(post.original_content) > 100 else post.original_content,
                "platform": analytics.platform,
                "views": analytics.views,
                "likes": analytics.likes,
                "comments": analytics.comments,
                "shares": analytics.shares,
                "engagement_rate": analytics.engagement_rate,
                "created_at": post.created_at.isoformat()
            }
            for post, analytics in rows
        ]

    @staticmethod
    async def get_analytics_over_time(
        db: AsyncSession,
        user_id: int,
        days: int = 30,
        platform: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get daily analytics aggregated over time"""
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get posts in date range
        posts_query = select(models.Post.id).where(
            and_(
                models.Post.user_id == user_id,
                models.Post.created_at >= start_date
            )
        )

        posts_result = await db.execute(posts_query)
        post_ids = [p[0] for p in posts_result.all()]

        if not post_ids:
            return []

        # Get analytics grouped by date
        query = select(
            func.date(models.PostAnalytics.fetched_at).label('date'),
            func.sum(models.PostAnalytics.views).label('views'),
            func.sum(models.PostAnalytics.likes).label('likes'),
            func.sum(models.PostAnalytics.comments).label('comments'),
            func.sum(models.PostAnalytics.shares).label('shares'),
            func.avg(models.PostAnalytics.engagement_rate).label(
                'avg_engagement_rate')
        ).where(
            models.PostAnalytics.post_id.in_(post_ids)
        ).group_by(
            func.date(models.PostAnalytics.fetched_at)
        ).order_by(
            func.date(models.PostAnalytics.fetched_at)
        )

        if platform:
            query = query.where(models.PostAnalytics.platform == platform)

        result = await db.execute(query)
        rows = result.all()

        return [
            {
                "date": row.date.isoformat(),
                "views": row.views or 0,
                "likes": row.likes or 0,
                "comments": row.comments or 0,
                "shares": row.shares or 0,
                "engagement_rate": float(row.avg_engagement_rate or 0.0)
            }
            for row in rows
        ]


class UserAnalyticsSummaryCRUD:
    @staticmethod
    async def get_or_create(db: AsyncSession, user_id: int, period: str, start_date: datetime, end_date: datetime) -> models.UserAnalyticsSummary:
        result = await db.execute(select(models.UserAnalyticsSummary).where(
            and_(
                models.UserAnalyticsSummary.user_id == user_id,
                models.UserAnalyticsSummary.period == period,
                models.UserAnalyticsSummary.start_date == start_date
            )
        ))
        summary = result.scalar_one_or_none()
        if not summary:
            summary = models.UserAnalyticsSummary(
                user_id=user_id,
                period=period,
                start_date=start_date,
                end_date=end_date,
                updated_at=datetime.utcnow()
            )
            db.add(summary)
            await db.commit()
            await db.refresh(summary)
        return summary

    @staticmethod
    async def update_summary(db: AsyncSession, summary_id: int, data: Dict):
        result = await db.execute(select(models.UserAnalyticsSummary).where(models.UserAnalyticsSummary.id == summary_id))
        summary = result.scalar_one_or_none()
        if summary:
            for key, value in data.items():
                setattr(summary, key, value)
            summary.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(summary)
        return summary
