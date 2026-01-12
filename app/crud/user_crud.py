from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, desc, select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
from .. import models, schemas
from app.utils.datetime_utils import make_timezone_naive, utcnow_naive
from app.services.auth_service import get_password_hash
class UserCRUD:
    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[models.User]:
        result = await db.execute(select(models.User).where(models.User.id == user_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[models.User]:
        result = await db.execute(select(models.User).where(models.User.email == email))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> Optional[models.User]:
        result = await db.execute(select(models.User).where(models.User.username == username))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_user(db: AsyncSession, user: schemas.UserCreate) -> models.User:
      
        
        db_user = models.User(
            email=user.email,
            username=user.username,
            hashed_password=get_password_hash(user.password)
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return db_user
    
    @staticmethod
    async def update_user(db: AsyncSession, user_id: int, user_update: schemas.UserUpdate) -> Optional[models.User]:
        db_user = await UserCRUD.get_user_by_id(db, user_id)
        if not db_user:
            return None
        
        update_data = user_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        await db.commit()
        await db.refresh(db_user)
        return db_user
    
    @staticmethod
    async def increment_post_count(db: AsyncSession, user_id: int) -> bool:
        db_user = await UserCRUD.get_user_by_id(db, user_id)
        if not db_user:
            return False
        
        db_user.posts_used += 1
        await db.commit()
        return True
    
    @staticmethod
    async def get_user_stats(db: AsyncSession, user_id: int) -> Dict[str, Any]:
        """Get comprehensive user statistics"""
        db_user = await UserCRUD.get_user_by_id(db, user_id)
        if not db_user:
            return {}
        
        # Get post counts by status
        result = await db.execute(
            select(
                models.Post.status,
                func.count().label("count")
            ).where(
                models.Post.user_id == user_id
            ).group_by(models.Post.status)
        )
        rows = result.all()
        status_counts = {row[0]: row[1] for row in rows}
        
        # Get connected platforms
        result = await db.execute(
            select(models.SocialConnection).where(
                and_(
                    models.SocialConnection.user_id == user_id,
                    models.SocialConnection.is_active == True
                )
            )
        )
        connections = result.scalars().all()
        
        return {
            "posts_used": db_user.posts_used,
            "posts_limit": db_user.posts_limit,
            "plan": db_user.plan,
            "status_breakdown": status_counts,
            "connected_platforms": len(connections),
            "platforms": [conn.platform for conn in connections]
        }


