from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, desc, select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
from .. import models, schemas
from app.utils.datetime_utils import make_timezone_naive, utcnow_naive
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
    async def get_post_by_id(db: AsyncSession,
                             post_id: int, 
                             user_id: Optional[int] = None
                             ) -> Optional[models.Post]:
        query = select(models.Post).where(models.Post.id == post_id)
        if user_id is not None:
            query = query.where(models.Post.user_id == user_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

  
    @staticmethod
    async def create_post(
        db: AsyncSession, 
        post: schemas.PostCreate,
        user_id: int
    ) -> models.Post:
        """Create a new post with support for platform-specific content and videos"""
        
        # Convert enhanced_content dict to JSON string
        enhanced_content_str = None
        if post.enhanced_content:
            enhanced_content_str = json.dumps(post.enhanced_content)
        
        # Convert platform_specific_content to JSON string
        platform_specific_content_str = None
        if post.platform_specific_content:
            platform_specific_content_str = json.dumps(post.platform_specific_content)
        
        # Convert lists to JSON strings
        image_urls_str = json.dumps(post.image_urls or [])
        video_urls_str = json.dumps(post.video_urls or [])
        platforms_str = json.dumps(post.platforms)
        
        # ✅ FIX: Ensure scheduled_for is timezone-naive
        scheduled_datetime = make_timezone_naive(post.scheduled_for)
        
        # ✅ FIX: Use timezone-naive datetime for created_at and updated_at
        now = utcnow_naive()
        
        db_post = models.Post(
            user_id=user_id,
            original_content=post.original_content,
            enhanced_content=enhanced_content_str,
            platform_specific_content=platform_specific_content_str,
            image_urls=image_urls_str,
            video_urls=video_urls_str,
            audio_file_url=post.audio_file_url,
            platforms=platforms_str,
            scheduled_for=scheduled_datetime,  # ✅ Timezone-naive
            status="scheduled" if scheduled_datetime else "draft",
            created_at=now,  # ✅ Timezone-naive
            updated_at=now   # ✅ Timezone-naive
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

