# app/routers/analytics.py
"""
Analytics API endpoints.
Provides access to post and user analytics.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app import models, schemas, auth
from app.database import get_async_db
from app.services.analytics.analytics_service import AnalyticsService
from app.crud.analytics_crud import AnalyticsCRUD

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/fetch/{post_id}", response_model=schemas.FetchAnalyticsResponse)
async def fetch_post_analytics(
    post_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Manually fetch/refresh analytics for a specific post.
    Fetches from all platforms where the post was published.
    """
    result = await AnalyticsService.fetch_post_analytics(
        db, post_id, current_user.id
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=404,
            detail=result.get("error", "Failed to fetch analytics")
        )
    
    return result


@router.get("/post/{post_id}", response_model=List[schemas.PostAnalyticsResponse])
async def get_post_analytics(
    post_id: int,
    platform: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get stored analytics for a specific post.
    Optionally filter by platform.
    """
    analytics = await AnalyticsCRUD.get_post_analytics(db, post_id, platform)
    
    if not analytics:
        raise HTTPException(
            status_code=404,
            detail="No analytics found for this post"
        )
    
    return analytics


@router.get("/dashboard", response_model=schemas.DashboardAnalyticsResponse)
async def get_dashboard_analytics(
    days: int = Query(default=30, ge=1, le=365),
    platform: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get comprehensive analytics dashboard for the current user.
    
    Returns:
    - Summary metrics (total views, engagement, etc.)
    - Top performing posts
    - Analytics trend over time
    """
    dashboard = await AnalyticsService.get_user_dashboard_analytics(
        db, current_user.id, days, platform
    )
    
    return dashboard


@router.get("/summary", response_model=schemas.AnalyticsSummaryResponse)
async def get_analytics_summary(
    days: int = Query(default=30, ge=1, le=365),
    platform: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get aggregated analytics summary for the user.
    """
    from datetime import datetime, timedelta
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    summary = await AnalyticsCRUD.get_user_analytics_summary(
        db, current_user.id, start_date, end_date, platform
    )
    
    return summary


@router.get("/top-posts", response_model=List[schemas.TopPerformingPost])
async def get_top_posts(
    limit: int = Query(default=10, ge=1, le=50),
    metric: str = Query(default="engagement_rate", regex="^(engagement_rate|views|likes)$"),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get top performing posts.
    Sort by: engagement_rate, views, or likes
    """
    top_posts = await AnalyticsCRUD.get_top_performing_posts(
        db, current_user.id, limit, metric
    )
    
    return top_posts


@router.get("/trends", response_model=List[schemas.AnalyticsOverTime])
async def get_analytics_trends(
    days: int = Query(default=30, ge=7, le=365),
    platform: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get analytics trends over time.
    Daily aggregated metrics.
    """
    trends = await AnalyticsCRUD.get_analytics_over_time(
        db, current_user.id, days, platform
    )
    
    return trends


@router.get("/comparison", response_model=schemas.PlatformComparisonResponse)
async def get_platform_comparison(
    days: int = Query(default=30, ge=1, le=365),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Compare performance across all platforms.
    Shows which platform performs best.
    """
    comparison = await AnalyticsService.get_platform_comparison(
        db, current_user.id, days
    )
    
    return comparison