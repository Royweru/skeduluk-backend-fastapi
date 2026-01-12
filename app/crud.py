# app/crud.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, desc, select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
from . import models, schemas
from app.utils.datetime_utils import make_timezone_naive, utcnow_naive

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

# app/crud/template_crud.py



class TemplateCRUD:
    """CRUD operations for templates"""
    
    @staticmethod
    async def create_template(
        db: AsyncSession,
        template: schemas.TemplateCreate,
        user_id: Optional[int] = None
    ) -> models.PostTemplate:
        """Create a new template"""
        
        # Convert Pydantic models to dicts
        variables_dict = None
        if template.variables:
            variables_dict = [v.model_dump() for v in template.variables]
        
        db_template = models.PostTemplate(
            user_id=user_id,
            name=template.name,
            description=template.description,
            category=template.category,
            content_template=template.content_template,
            variables=variables_dict,
            platform_variations=template.platform_variations,
            supported_platforms=template.supported_platforms,
            tone=template.tone,
            suggested_hashtags=template.suggested_hashtags,
            suggested_media_type=template.suggested_media_type,
            is_public=template.is_public,
            is_system=False if user_id else True,
            thumbnail_url=template.thumbnail_url,
            color_scheme=template.color_scheme,
            icon=template.icon
        )
        
        db.add(db_template)
        await db.commit()
        await db.refresh(db_template)
        
        return db_template
    
    @staticmethod
    async def get_template_by_id(
        db: AsyncSession,
        template_id: int,
        user_id: Optional[int] = None
    ) -> Optional[models.PostTemplate]:
        """Get template by ID"""
        query = select(models.PostTemplate).where(
            models.PostTemplate.id == template_id
        )
        
        # If user_id provided, only return if it's theirs or a system template
        if user_id:
            query = query.where(
                or_(
                    models.PostTemplate.user_id == user_id,
                    models.PostTemplate.is_system == True,
                    and_(
                        models.PostTemplate.is_public == True,
                        models.PostTemplate.user_id.isnot(None)
                    )
                )
            )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def search_templates(
        db: AsyncSession,
        user_id: int,
        search_request: schemas.TemplateSearchRequest
    ) -> tuple[List[models.PostTemplate], int]:
        """Search templates with filters"""
        
        # Base query
        query = select(models.PostTemplate).where(
            or_(
                models.PostTemplate.user_id == user_id,
                models.PostTemplate.is_system == True if search_request.include_system else False,
                and_(
                    models.PostTemplate.is_public == True,
                    models.PostTemplate.user_id.isnot(None)
                ) if search_request.include_community else False
            )
        )
        
        # Apply filters
        if search_request.query:
            search_term = f"%{search_request.query}%"
            query = query.where(
                or_(
                    models.PostTemplate.name.ilike(search_term),
                    models.PostTemplate.description.ilike(search_term)
                )
            )
        
        if search_request.category:
            query = query.where(models.PostTemplate.category == search_request.category)
        
        if search_request.tone:
            query = query.where(models.PostTemplate.tone == search_request.tone)
        
        if search_request.is_favorite is not None:
            query = query.where(models.PostTemplate.is_favorite == search_request.is_favorite)
        
        if search_request.folder_id:
            query = query.where(models.PostTemplate.folder_id == search_request.folder_id)
        
        # Platform filter (check if any of the requested platforms are in supported_platforms JSON)
        if search_request.platforms:
            # This is a bit tricky with JSON columns - we'll need to fetch and filter in Python
            # For now, we'll skip this filter in SQL and handle it in Python
            pass
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Sort
        if search_request.sort_by == "name":
            sort_col = models.PostTemplate.name
        elif search_request.sort_by == "usage_count":
            sort_col = models.PostTemplate.usage_count
        elif search_request.sort_by == "success_rate":
            sort_col = models.PostTemplate.success_rate
        else:
            sort_col = models.PostTemplate.created_at
        
        if search_request.sort_order == "asc":
            query = query.order_by(asc(sort_col))
        else:
            query = query.order_by(desc(sort_col))
        
        # Pagination
        query = query.offset(search_request.offset).limit(search_request.limit)
        
        result = await db.execute(query)
        templates = result.scalars().all()
        
        # Filter by platforms if specified (post-SQL filtering)
        if search_request.platforms:
            templates = [
                t for t in templates
                if any(p in t.supported_platforms for p in search_request.platforms)
            ]
        
        return list(templates), total
    
    @staticmethod
    async def update_template(
        db: AsyncSession,
        template_id: int,
        user_id: int,
        template_update: schemas.TemplateUpdate
    ) -> Optional[models.PostTemplate]:
        """Update a template"""
        
        query = select(models.PostTemplate).where(
            and_(
                models.PostTemplate.id == template_id,
                models.PostTemplate.user_id == user_id
            )
        )
        
        result = await db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            return None
        
        # Update fields
        update_data = template_update.model_dump(exclude_unset=True)
        
        # Handle variables specially
        if 'variables' in update_data and update_data['variables']:
            update_data['variables'] = [v.model_dump() if hasattr(v, 'model_dump') else v 
                                       for v in update_data['variables']]
        
        for field, value in update_data.items():
            setattr(template, field, value)
        
        template.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(template)
        
        return template
    
    @staticmethod
    async def delete_template(
        db: AsyncSession,
        template_id: int,
        user_id: int
    ) -> bool:
        """Delete a template"""
        
        query = select(models.PostTemplate).where(
            and_(
                models.PostTemplate.id == template_id,
                models.PostTemplate.user_id == user_id
            )
        )
        
        result = await db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            return False
        
        await db.delete(template)
        await db.commit()
        
        return True
    
    @staticmethod
    async def use_template(
        db: AsyncSession,
        template_id: int,
        user_id: int
    ) -> Optional[models.PostTemplate]:
        """Increment usage count and update last_used_at"""
        
        template = await TemplateCRUD.get_template_by_id(db, template_id, user_id)
        
        if not template:
            return None
        
        template.usage_count += 1
        template.last_used_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(template)
        
        return template
    
    @staticmethod
    async def toggle_favorite(
        db: AsyncSession,
        template_id: int,
        user_id: int
    ) -> Optional[models.PostTemplate]:
        """Toggle favorite status"""
        
        query = select(models.PostTemplate).where(
            and_(
                models.PostTemplate.id == template_id,
                models.PostTemplate.user_id == user_id
            )
        )
        
        result = await db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            return None
        
        template.is_favorite = not template.is_favorite
        await db.commit()
        await db.refresh(template)
        
        return template
    
    @staticmethod
    async def get_template_analytics(
        db: AsyncSession,
        template_id: int,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get analytics for a template"""
        
        template = await TemplateCRUD.get_template_by_id(db, template_id, user_id)
        if not template:
            return None
        
        # Get analytics records
        query = select(models.TemplateAnalytics).where(
            models.TemplateAnalytics.template_id == template_id
        )
        
        result = await db.execute(query)
        analytics = result.scalars().all()
        
        if not analytics:
            return {
                "total_uses": template.usage_count,
                "success_rate": 0,
                "avg_engagement_rate": 0,
                "platform_breakdown": {},
                "recent_posts": [],
                "engagement_trend": []
            }
        
        # Calculate metrics
        total_engagement = sum(a.engagement_rate for a in analytics)
        avg_engagement = total_engagement // len(analytics) if analytics else 0
        
        # Platform breakdown
        platform_breakdown = {}
        for a in analytics:
            platform_breakdown[a.platform] = platform_breakdown.get(a.platform, 0) + 1
        
        # Recent posts (last 10)
        recent = sorted(analytics, key=lambda x: x.posted_at, reverse=True)[:10]
        recent_posts = [
            {
                "post_id": a.post_id,
                "platform": a.platform,
                "engagement_rate": a.engagement_rate,
                "likes": a.likes,
                "comments": a.comments,
                "shares": a.shares,
                "posted_at": a.posted_at.isoformat()
            }
            for a in recent
        ]
        
        # Engagement trend (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_analytics = [a for a in analytics if a.posted_at >= thirty_days_ago]
        
        engagement_trend = []
        for a in recent_analytics:
            engagement_trend.append({
                "date": a.posted_at.strftime("%Y-%m-%d"),
                "engagement_rate": a.engagement_rate
            })
        
        return {
            "total_uses": template.usage_count,
            "success_rate": template.success_rate,
            "avg_engagement_rate": avg_engagement,
            "platform_breakdown": platform_breakdown,
            "recent_posts": recent_posts,
            "engagement_trend": engagement_trend
        }
    
    @staticmethod
    async def get_categories_with_counts(
        db: AsyncSession,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """Get all categories with template counts"""
        
        query = select(
            models.PostTemplate.category,
            func.count(models.PostTemplate.id).label('count')
        ).where(
            or_(
                models.PostTemplate.user_id == user_id,
                models.PostTemplate.is_system == True
            )
        ).group_by(models.PostTemplate.category)
        
        result = await db.execute(query)
        rows = result.all()
        
        return [
            {"category": row.category, "count": row.count}
            for row in rows
        ]


class TemplateFolderCRUD:
    """CRUD operations for template folders"""
    
    @staticmethod
    async def create_folder(
        db: AsyncSession,
        folder: schemas.TemplateFolderCreate,
        user_id: int
    ) -> models.TemplateFolder:
        """Create a new folder"""
        
        db_folder = models.TemplateFolder(
            user_id=user_id,
            name=folder.name,
            description=folder.description,
            color=folder.color,
            icon=folder.icon
        )
        
        db.add(db_folder)
        await db.commit()
        await db.refresh(db_folder)
        
        return db_folder
    
    @staticmethod
    async def get_folders(
        db: AsyncSession,
        user_id: int
    ) -> List[models.TemplateFolder]:
        """Get all folders for a user"""
        
        query = select(models.TemplateFolder).where(
            models.TemplateFolder.user_id == user_id
        ).order_by(models.TemplateFolder.created_at.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def delete_folder(
        db: AsyncSession,
        folder_id: int,
        user_id: int
    ) -> bool:
        """Delete a folder (templates in folder will have folder_id set to NULL)"""
        
        query = select(models.TemplateFolder).where(
            and_(
                models.TemplateFolder.id == folder_id,
                models.TemplateFolder.user_id == user_id
            )
        )
        
        result = await db.execute(query)
        folder = result.scalar_one_or_none()
        
        if not folder:
            return False
        
        await db.delete(folder)
        await db.commit()
        
        return True
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