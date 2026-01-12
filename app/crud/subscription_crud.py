from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, desc, select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
from .. import models, schemas
from app.utils.datetime_utils import make_timezone_naive, utcnow_naive
class SubscriptionCRUD:
    @staticmethod
    async def get_active_subscription(db: AsyncSession, user_id: int) -> Optional[models.Subscription]:
        result = await db.execute(
            select(models.Subscription).where(
                and_(
                    models.Subscription.user_id == user_id,
                    models.Subscription.status == "active",
                    models.Subscription.ends_at > datetime.utcnow()
                )
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_subscription(
        db: AsyncSession, 
        subscription: schemas.SubscriptionCreate, 
        user_id: int
    ) -> models.Subscription:
        # Calculate end date based on plan
        now = datetime.utcnow()
        plan_durations = {
            "basic": 30,
            "pro": 30,
            "enterprise": 365,
            "trial": 7
        }
        days = plan_durations.get(subscription.plan, 30)
        ends_at = now + timedelta(days=days)
        
        db_subscription = models.Subscription(
            user_id=user_id,
            plan=subscription.plan,
            amount=subscription.amount,
            currency=subscription.currency,
            payment_method=subscription.payment_method,
            payment_reference=subscription.payment_reference,
            starts_at=now,
            ends_at=ends_at,
            status="active"
        )
        db.add(db_subscription)
        await db.commit()
        await db.refresh(db_subscription)
        
        # Update user's plan and post limit
        user = await UserCRUD.get_user_by_id(db, user_id)
        if user:
            user.plan = subscription.plan
            plan_limits = {
                "free": 10,
                "basic": 50,
                "pro": 200,
                "enterprise": 1000
            }
            user.posts_limit = plan_limits.get(subscription.plan, 10)
            await db.commit()
        
        return db_subscription




