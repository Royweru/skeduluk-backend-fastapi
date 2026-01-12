from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, desc, select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
from .. import models, schemas
from app.utils.datetime_utils import make_timezone_naive, utcnow_naive



class SocialConnectionCRUD:
    @staticmethod
    async def get_connections_by_user(
        db: AsyncSession, 
        user_id: int, 
        platform: Optional[str] = None
    ) -> List[models.SocialConnection]:
        query = select(models.SocialConnection).where(
            and_(
                models.SocialConnection.user_id == user_id,
                models.SocialConnection.is_active == True
            )
        )
        
        if platform:
            query = query.where(models.SocialConnection.platform == platform.upper())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_connection_by_platform(
        db: AsyncSession,
        user_id: int,
        platform: str
    ) -> Optional[models.SocialConnection]:
        """Get a specific platform connection"""
        result = await db.execute(
            select(models.SocialConnection).where(
                and_(
                    models.SocialConnection.user_id == user_id,
                    models.SocialConnection.platform == platform.upper(),
                    models.SocialConnection.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_connection(
        db: AsyncSession, 
        user_id: int, 
        connection: schemas.SocialConnectionBase,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None
    ) -> models.SocialConnection:
        db_connection = models.SocialConnection(
            user_id=user_id,
            platform=connection.platform.upper(),
            platform_user_id=connection.platform_user_id,
            platform_username=connection.username,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            is_active=True,
            last_synced=datetime.utcnow()
        )
        db.add(db_connection)
        await db.commit()
        await db.refresh(db_connection)
        return db_connection
    
    @staticmethod
    async def deactivate_connection(db: AsyncSession, connection_id: int, user_id: int) -> bool:
        db_connection = await db.execute(
            select(models.SocialConnection).where(
                and_(
                    models.SocialConnection.id == connection_id,
                    models.SocialConnection.user_id == user_id
                )
            )
        )
        connection = db_connection.scalar_one_or_none()
        
        if not connection:
            return False
        
        connection.is_active = False
        await db.commit()
        return True
    
    @staticmethod
    async def update_connection_tokens(
        db: AsyncSession,
        connection_id: int,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None
    ) -> bool:
        """Update connection OAuth tokens"""
        result = await db.execute(
            select(models.SocialConnection).where(
                models.SocialConnection.id == connection_id
            )
        )
        connection = result.scalar_one_or_none()
        
        if not connection:
            return False
        
        connection.access_token = access_token
        if refresh_token:
            connection.refresh_token = refresh_token
        if token_expires_at:
            connection.token_expires_at = token_expires_at
        connection.last_synced = datetime.utcnow()
        
        await db.commit()
        return True