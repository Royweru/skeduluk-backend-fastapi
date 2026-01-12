# app/routers/templates.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import json

from app import models, schemas, auth
from app.database import get_async_db
from app.crud import TemplateCRUD, TemplateFolderCRUD
from app.services.ai_service import ai_service

router = APIRouter(prefix="/templates", tags=["templates"])


# ============================================================================
# CRITICAL FIX: Put specific routes BEFORE parameterized routes
# Order matters in FastAPI routing!
# ============================================================================

# ✅ STEP 1: All /templates/SPECIFIC routes come FIRST
@router.get("/search", response_model=schemas.TemplateSearchResponse)
async def search_templates(
    query: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    tone: Optional[str] = Query(None),
    platforms: Optional[str] = Query(None),
    is_favorite: Optional[bool] = Query(None),
    folder_id: Optional[int] = Query(None),
    include_system: bool = Query(True),
    include_community: bool = Query(False),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Search templates with advanced filters"""
    
    platforms_list = platforms.split(',') if platforms else None
    
    search_request = schemas.TemplateSearchRequest(
        query=query,
        category=category,
        tone=tone,
        platforms=platforms_list,
        is_favorite=is_favorite,
        folder_id=folder_id,
        include_system=include_system,
        include_community=include_community,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset
    )
    
    templates, total = await TemplateCRUD.search_templates(db, current_user.id, search_request)
    
    # ✅ FIX: Convert SQLAlchemy models to Pydantic schemas
    template_responses = [
        schemas.TemplateResponse.model_validate(t) for t in templates
    ]
    
    return schemas.TemplateSearchResponse(
        templates=template_responses,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/categories/list")
async def get_categories(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get all categories with template counts"""
    categories = await TemplateCRUD.get_categories_with_counts(db, current_user.id)
    return {"categories": categories}


# ============================================================================
# FOLDER ROUTES - Must come before /{template_id}
# ============================================================================

@router.post("/folders", response_model=schemas.TemplateFolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    folder: schemas.TemplateFolderCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Create a new template folder"""
    db_folder = await TemplateFolderCRUD.create_folder(db, folder, current_user.id)
    return schemas.TemplateFolderResponse.model_validate(db_folder)


@router.get("/folders", response_model=List[schemas.TemplateFolderResponse])
async def get_folders(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get all folders for current user"""
    folders = await TemplateFolderCRUD.get_folders(db, current_user.id)
    return [schemas.TemplateFolderResponse.model_validate(f) for f in folders]


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Delete a folder"""
    success = await TemplateFolderCRUD.delete_folder(db, folder_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Folder not found")
    return None


# ============================================================================
# TEMPLATE CRUD ENDPOINTS - Parameterized routes come AFTER specific routes
# ============================================================================

@router.post("/", response_model=schemas.TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template: schemas.TemplateCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Create a new template"""
    try:
        db_template = await TemplateCRUD.create_template(db, template, current_user.id)
        return schemas.TemplateResponse.model_validate(db_template)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ STEP 2: Parameterized routes like /{template_id} come LAST
@router.get("/{template_id}", response_model=schemas.TemplateResponse)
async def get_template(
    template_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get a specific template by ID"""
    template = await TemplateCRUD.get_template_by_id(db, template_id, current_user.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return schemas.TemplateResponse.model_validate(template)


@router.put("/{template_id}", response_model=schemas.TemplateResponse)
async def update_template(
    template_id: int,
    template_update: schemas.TemplateUpdate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Update a template (only your own templates)"""
    template = await TemplateCRUD.update_template(db, template_id, current_user.id, template_update)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found or you don't have permission")
    return schemas.TemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Delete a template"""
    success = await TemplateCRUD.delete_template(db, template_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found or you don't have permission")
    return None


@router.post("/{template_id}/favorite", response_model=schemas.TemplateResponse)
async def toggle_favorite(
    template_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Toggle favorite status of a template"""
    template = await TemplateCRUD.toggle_favorite(db, template_id, current_user.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return schemas.TemplateResponse.model_validate(template)


# ============================================================================
# TEMPLATE USAGE ENDPOINTS
# ============================================================================

@router.post("/use/{template_id}", response_model=schemas.PostCreateResponse)
async def use_template(
    template_id: int,
    use_request: schemas.TemplateUseRequest,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Use a template to create a post"""
    
    # Get template
    template = await TemplateCRUD.get_template_by_id(db, template_id, current_user.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Replace variables in content
    content = template.content_template
    for var_name, var_value in use_request.variable_values.items():
        content = content.replace(f"{{{var_name}}}", var_value)
    
    # Check for unreplaced variables
    import re
    remaining_vars = re.findall(r'\{(\w+)\}', content)
    if remaining_vars:
        raise HTTPException(
            status_code=400,
            detail=f"Missing values for variables: {', '.join(remaining_vars)}"
        )
    
    # Platform-specific variations
    platform_specific_content = {}
    if template.platform_variations:
        for platform, variation in template.platform_variations.items():
            if platform in use_request.platforms:
                for var_name, var_value in use_request.variable_values.items():
                    variation = variation.replace(f"{{{var_name}}}", var_value)
                platform_specific_content[platform.lower()] = variation
    
    # AI Enhancement (optional)
    enhanced_content = None
    if use_request.use_ai_enhancement:
        try:
            enhancements = []
            for platform in use_request.platforms:
                enhanced = await ai_service.enhance_content(
                    content=platform_specific_content.get(platform.lower(), content),
                    platform=platform.upper(),
                    tone=template.tone,
                    include_hashtags=bool(template.suggested_hashtags),
                    include_emojis=template.tone in ['casual', 'humorous', 'friendly']
                )
                enhancements.append({
                    "platform": platform.upper(),
                    "enhanced_content": enhanced
                })
            
            enhanced_content = {
                e["platform"].lower(): e["enhanced_content"]
                for e in enhancements
            }
        except Exception as e:
            print(f"AI enhancement error: {e}")
    
    # Create post
    from app.services.post_service import PostService
    
    post_data = schemas.PostCreate(
        original_content=content,
        platforms=use_request.platforms,
        scheduled_for=use_request.scheduled_for,
        enhanced_content=enhanced_content or platform_specific_content,
        image_urls=use_request.images or [],
        video_urls=use_request.videos or []
    )
    
    post = await PostService.create_post(db, post_data, current_user.id)
    
    # Update template usage
    await TemplateCRUD.use_template(db, template_id, current_user.id)
    
    # Convert to response
    post_response = schemas.PostResponse(
        id=post.id,
        user_id=post.user_id,
        original_content=post.original_content,
        platforms=json.loads(post.platforms) if isinstance(post.platforms, str) else post.platforms,
        scheduled_for=post.scheduled_for,
        enhanced_content=json.loads(post.enhanced_content) if post.enhanced_content and isinstance(post.enhanced_content, str) else post.enhanced_content,
        image_urls=json.loads(post.image_urls) if post.image_urls and isinstance(post.image_urls, str) else post.image_urls or [],
        video_urls=json.loads(post.video_urls) if post.video_urls and isinstance(post.video_urls, str) else post.video_urls or [],
        audio_file_url=post.audio_file_url,
        status=post.status,
        error_message=post.error_message,
        created_at=post.created_at,
        updated_at=post.updated_at
    )
    
    response_data = post_response.model_dump()
    response_data["message"] = f"Post created from template: {template.name}"
    
    return schemas.PostCreateResponse(**response_data)


# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/{template_id}/analytics", response_model=schemas.TemplateAnalyticsResponse)
async def get_template_analytics(
    template_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get analytics for a template"""
    analytics = await TemplateCRUD.get_template_analytics(db, template_id, current_user.id)
    if analytics is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return analytics