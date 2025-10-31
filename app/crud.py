# app/crud.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
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

class PostCRUD:
    @staticmethod
    async def get_posts_by_user(
        db: AsyncSession, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[str] = None,
        platform: Optional[str] = None
    ) -> List[models.Post]:
        query = select(models.Post).where(models.Post.user_id == user_id)
        
        if status:
            query = query.where(models.Post.status == status)
        
        if platform:
            # Filter posts that include the specified platform
            query = query.where(models.Post.platforms.contains([platform]))
        
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
        post: schemas.PostCreate,  # This object has all the data we need
        user_id: int
        
    ) -> models.Post:
        """Create a new post with support for platform-specific content and videos"""
        
        # --- FIX FOR TYPE MISMATCH ---
        # Your 'enhanced_content' column is Text, but your schema sends a dict.
        # We must convert the dict to a JSON string to store it in a Text column.
        enhanced_content_str = None
        if post.enhanced_content:
            enhanced_content_str = json.dumps(post.enhanced_content)
        
        db_post = models.Post(
            user_id=user_id,
            original_content=post.original_content,
            
            # --- FIX FOR DATA LOSS ---
            # Use the data from the 'post' schema object, not separate arguments
            enhanced_content=enhanced_content_str,
            platform_specific_content=post.platform_specific_content,
            image_urls=post.image_urls or [],
            video_urls=post.video_urls or [], # You added this field in the schema, so let's use it
            audio_file_url=post.audio_file_url,
            platforms=post.platforms,
            scheduled_for=post.scheduled_for,
            status="scheduled" if post.scheduled_for else "draft",
            created_at=datetime.utcnow()
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
        
        db_post.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(db_post)
        return db_post
    
    @staticmethod
    async def delete_post(db: AsyncSession, post_id: int, user_id: int) -> bool:
        """Delete a post"""
        db_post = await PostCRUD.get_post_by_id(db, post_id, user_id)
        if not db_post:
            return False
        
        await db.delete(db_post)
        await db.commit()
        return True
    
    @staticmethod
    async def get_scheduled_posts(db: AsyncSession, limit: int = 50) -> List[models.Post]:
        """Get posts that are scheduled and ready to be published"""
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
        error_messages: Optional[Dict[str, str]] = None,
        published_urls: Optional[Dict[str, str]] = None
    ) -> bool:
        """Update post status with optional error messages and published URLs"""
        db_post = await db.execute(
            select(models.Post).where(models.Post.id == post_id)
        )
        post = db_post.scalar_one_or_none()
        
        if not post:
            return False
        
        post.status = status
        if error_messages:
            post.error_messages = error_messages
        if published_urls:
            post.published_urls = published_urls
        if status == "posted":
            post.published_at = datetime.utcnow()
        post.updated_at = datetime.utcnow()
        
        await db.commit()
        return True
    
    @staticmethod
    async def get_posts_by_date_range(
        db: AsyncSession,
        user_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[models.Post]:
        """Get posts within a date range (for calendar view)"""
        result = await db.execute(
            select(models.Post).where(
                and_(
                    models.Post.user_id == user_id,
                    or_(
                        and_(
                            models.Post.scheduled_for >= start_date,
                            models.Post.scheduled_for <= end_date
                        ),
                        and_(
                            models.Post.published_at >= start_date,
                            models.Post.published_at <= end_date
                        )
                    )
                )
            ).order_by(models.Post.scheduled_for.desc())
        )
        return result.scalars().all()
    
    @staticmethod
    async def duplicate_post(
        db: AsyncSession,
        post_id: int,
        user_id: int
    ) -> Optional[models.Post]:
        """Create a duplicate of an existing post"""
        original = await PostCRUD.get_post_by_id(db, post_id, user_id)
        if not original:
            return None
        
        duplicate = models.Post(
            user_id=user_id,
            original_content=original.original_content,
            platforms=original.platforms,
            image_urls=original.image_urls,
            video_urls=original.video_urls,
            audio_file_url=original.audio_file_url,
            platform_specific_content=original.platform_specific_content,
            ai_enhanced=original.ai_enhanced,
            ai_suggestions=original.ai_suggestions,
            status="draft",
            created_at=datetime.utcnow()
        )
        
        db.add(duplicate)
        await db.commit()
        await db.refresh(duplicate)
        
        return duplicate
    
    @staticmethod
    async def get_post_analytics(
        db: AsyncSession,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get post analytics for the specified period"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get posts in date range
        result = await db.execute(
            select(models.Post).where(
                and_(
                    models.Post.user_id == user_id,
                    models.Post.created_at >= start_date
                )
            )
        )
        posts = result.scalars().all()
        
        # Calculate statistics
        total_posts = len(posts)
        status_distribution = {}
        platform_distribution = {}
        
        for post in posts:
            # Status counts
            status_distribution[post.status] = status_distribution.get(post.status, 0) + 1
            
            # Platform counts
            for platform in post.platforms:
                platform_distribution[platform] = platform_distribution.get(platform, 0) + 1
        
        # Media statistics
        posts_with_images = sum(1 for p in posts if p.image_urls)
        posts_with_videos = sum(1 for p in posts if p.video_urls)
        total_images = sum(len(p.image_urls or []) for p in posts)
        total_videos = sum(len(p.video_urls or []) for p in posts)
        
        return {
            "period_days": days,
            "total_posts": total_posts,
            "status_distribution": status_distribution,
            "platform_distribution": platform_distribution,
            "media_stats": {
                "posts_with_images": posts_with_images,
                "posts_with_videos": posts_with_videos,
                "total_images": total_images,
                "total_videos": total_videos
            },
            "ai_enhanced_count": sum(1 for p in posts if p.ai_enhanced),
            "scheduled_count": sum(1 for p in posts if p.status == "scheduled"),
            "published_count": sum(1 for p in posts if p.status == "posted")
        }

class PostResultCRUD:
    @staticmethod
    async def create_result(
        db: AsyncSession, 
        post_id: int, 
        platform: str,
        status: str,
        platform_post_id: Optional[str] = None,
        platform_post_url: Optional[str] = None,
        error_message: Optional[str] = None,
        content_used: Optional[str] = None
    ) -> models.PostResult:
        """Create a post result entry for tracking platform-specific outcomes"""
        db_result = models.PostResult(
            post_id=post_id,
            platform=platform,
            platform_post_id=platform_post_id,
            platform_post_url=platform_post_url,
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
    
    @staticmethod
    async def get_result_by_platform(
        db: AsyncSession,
        post_id: int,
        platform: str
    ) -> Optional[models.PostResult]:
        """Get result for a specific platform"""
        result = await db.execute(
            select(models.PostResult).where(
                and_(
                    models.PostResult.post_id == post_id,
                    models.PostResult.platform == platform
                )
            )
        )
        return result.scalar_one_or_none()

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
            is_public=template.is_public,
            created_at=datetime.utcnow()
        )
        db.add(db_template)
        await db.commit()
        await db.refresh(db_template)
        return db_template
    
    @staticmethod
    async def delete_template(
        db: AsyncSession,
        template_id: int,
        user_id: int
    ) -> bool:
        """Delete a template"""
        result = await db.execute(
            select(models.PostTemplate).where(
                and_(
                    models.PostTemplate.id == template_id,
                    models.PostTemplate.user_id == user_id
                )
            )
        )
        template = result.scalar_one_or_none()
        
        if not template:
            return False
        
        await db.delete(template)
        await db.commit()
        return True