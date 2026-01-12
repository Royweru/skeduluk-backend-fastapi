from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, desc, select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
from .. import models ,schemas
from app.utils.datetime_utils import make_timezone_naive, utcnow_naive

class PostAnalyticsCRUD:
    @staticmethod
    async def create(db: AsyncSession, post_id: int, platform: str, metrics: Dict) -> models.PostAnalytics:
        analytics = models.PostAnalytics(
            post_id=post_id,
            platform=platform,
            metrics=metrics,
            fetched_at=datetime.utcnow()
        )
        db.add(analytics)
        await db.commit()
        await db.refresh(analytics)
        return analytics

    @staticmethod
    async def get_by_post(db: AsyncSession, post_id: int) -> List[models.PostAnalytics]:
        result = await db.execute(select(models.PostAnalytics).where(models.PostAnalytics.post_id == post_id))
        return result.scalars().all()

    @staticmethod
    async def update_metrics(db: AsyncSession, analytics_id: int, metrics: Dict, error: Optional[str] = None):
        result = await db.execute(select(models.PostAnalytics).where(models.PostAnalytics.id == analytics_id))
        analytics = result.scalar_one_or_none()
        if analytics:
            analytics.metrics = metrics
            analytics.error = error
            analytics.fetched_at = datetime.utcnow()
            await db.commit()
            await db.refresh(analytics)
        return analytics

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