# app/crud.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from . import models, schemas

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
        from .auth import get_password_hash
        
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
            username=connection.username,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at
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

class PostCRUD:
    @staticmethod
    async def get_posts_by_user(
        db: AsyncSession, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[models.Post]:
        query = select(models.Post).where(models.Post.user_id == user_id)
        
        if status:
            query = query.where(models.Post.status == status)
        
        query = query.offset(skip).limit(limit).order_by(models.Post.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_post_by_id(db: AsyncSession, post_id: int, user_id: int) -> Optional[models.Post]:
        result = await db.execute(
            select(models.Post).where(
                and_(
                    models.Post.id == post_id,
                    models.Post.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_post(
        db: AsyncSession, 
        post: schemas.PostCreate, 
        user_id: int
    ) -> models.Post:
        db_post = models.Post(
            user_id=user_id,
            original_content=post.original_content,
            enhanced_content=post.enhanced_content,
            image_urls=post.image_urls,
            audio_file_url=post.audio_file_url,
            platforms=post.platforms,
            scheduled_for=post.scheduled_for,
            status="scheduled" if post.scheduled_for else "ready"
        )
        db.add(db_post)
        await db.commit()
        await db.refresh(db_post)
        
        # Update user's post count
        await UserCRUD.increment_post_count(db, user_id)
        
        return db_post
    
    @staticmethod
    async def update_post(
        db: AsyncSession, 
        post_id: int, 
        user_id: int, 
        post_update: schemas.PostUpdate
    ) -> Optional[models.Post]:
        db_post = await PostCRUD.get_post_by_id(db, post_id, user_id)
        if not db_post:
            return None
        
        update_data = post_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_post, field, value)
        
        await db.commit()
        await db.refresh(db_post)
        return db_post
    
    @staticmethod
    async def get_scheduled_posts(db: AsyncSession, limit: int = 50) -> List[models.Post]:
        now = datetime.utcnow()
        result = await db.execute(
            select(models.Post).where(
                and_(
                    models.Post.status == "scheduled",
                    models.Post.scheduled_for <= now
                )
            ).limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def update_post_status(
        db: AsyncSession, 
        post_id: int, 
        status: str, 
        error_message: Optional[str] = None
    ) -> bool:
        db_post = await db.execute(
            select(models.Post).where(models.Post.id == post_id)
        )
        post = db_post.scalar_one_or_none()
        
        if not post:
            return False
        
        post.status = status
        post.error_message = error_message
        post.updated_at = datetime.utcnow()
        
        await db.commit()
        return True

class PostResultCRUD:
    @staticmethod
    async def create_result(
        db: AsyncSession, 
        post_id: int, 
        platform: str,
        status: str,
        platform_post_id: Optional[str] = None,
        error_message: Optional[str] = None,
        content_used: Optional[str] = None
    ) -> models.PostResult:
        db_result = models.PostResult(
            post_id=post_id,
            platform=platform,
            platform_post_id=platform_post_id,
            status=status,
            error_message=error_message,
            posted_at=datetime.utcnow() if status == "posted" else None,
            content_used=content_used
        )
        db.add(db_result)
        await db.commit()
        await db.refresh(db_result)
        return db_result
    
    @staticmethod
    async def get_results_by_post(db: AsyncSession, post_id: int) -> List[models.PostResult]:
        result = await db.execute(
            select(models.PostResult).where(models.PostResult.post_id == post_id)
        )
        return result.scalars().all()

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
        if subscription.plan == "basic":
            ends_at = now + timedelta(days=30)
        elif subscription.plan == "pro":
            ends_at = now + timedelta(days=30)
        elif subscription.plan == "enterprise":
            ends_at = now + timedelta(days=365)
        else:
            ends_at = now + timedelta(days=7)  # Default for trial
        
        db_subscription = models.Subscription(
            user_id=user_id,
            plan=subscription.plan,
            amount=subscription.amount,
            currency=subscription.currency,
            payment_method=subscription.payment_method,
            payment_reference=subscription.payment_reference,
            starts_at=now,
            ends_at=ends_at
        )
        db.add(db_subscription)
        await db.commit()
        await db.refresh(db_subscription)
        
        # Update user's plan and post limit
        user = await UserCRUD.get_user_by_id(db, user_id)
        if user:
            user.plan = subscription.plan
            if subscription.plan == "basic":
                user.posts_limit = 50
            elif subscription.plan == "pro":
                user.posts_limit = 200
            elif subscription.plan == "enterprise":
                user.posts_limit = 1000
            await db.commit()
        
        return db_subscription

class TemplateCRUD:
    @staticmethod
    async def get_templates_by_user(
        db: AsyncSession, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[models.PostTemplate]:
        result = await db.execute(
            select(models.PostTemplate)
            .where(models.PostTemplate.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(models.PostTemplate.created_at.desc())
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_public_templates(db: AsyncSession, limit: int = 50) -> List[models.PostTemplate]:
        result = await db.execute(
            select(models.PostTemplate)
            .where(models.PostTemplate.is_public == True)
            .limit(limit)
            .order_by(models.PostTemplate.created_at.desc())
        )
        return result.scalars().all()
    
    @staticmethod
    async def create_template(
        db: AsyncSession, 
        template: schemas.TemplateCreate, 
        user_id: int
    ) -> models.PostTemplate:
        db_template = models.PostTemplate(
            user_id=user_id,
            name=template.name,
            content=template.content,
            platforms=template.platforms,
            is_public=template.is_public
        )
        db.add(db_template)
        await db.commit()
        await db.refresh(db_template)
        return db_template