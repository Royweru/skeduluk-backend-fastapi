
# app/crud/template_crud.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, desc, select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
from .. import models, schemas
from app.utils.datetime_utils import make_timezone_naive, utcnow_naive
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