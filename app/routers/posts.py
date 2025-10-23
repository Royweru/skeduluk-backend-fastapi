# app/routers/posts.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime
from ..services import ai_service
from .. import auth, schemas, models
from ..database import get_async_db
from ..services.post_service import PostService
from ..crud import PostCRUD
router = APIRouter(prefix="/posts", tags=["posts"])

@router.post("/", response_model=schemas.PostResponse)
async def create_post(
    original_content: str = Form(...),
    platforms: str = Form(...),
    scheduled_for: Optional[str] = Form(None),
    enhanced_content: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    audio: Optional[UploadFile] = File(None),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Create a new post"""
    # Parse JSON strings
    import json
    platforms_list = json.loads(platforms)
    enhanced_content_dict = json.loads(enhanced_content) if enhanced_content else None
    
    # Handle file uploads
    image_urls = []
    if images:
        image_urls = await PostService.upload_images(images, current_user.id)
    
    audio_file_url = None
    if audio:
        audio_file_url = await PostService.upload_audio(audio, current_user.id)
        # Transcribe audio if provided
        transcription = await PostService.transcribe_audio(audio_file_url)
        if transcription:
            original_content = f"{original_content}\n\n[Audio transcription]: {transcription}"
    
    # Create post
    post_data = schemas.PostCreate(
        original_content=original_content,
        platforms=platforms_list,
        scheduled_for=datetime.fromisoformat(scheduled_for) if scheduled_for else None,
        enhanced_content=enhanced_content_dict,
        image_urls=image_urls,
        audio_file_url=audio_file_url
    )
    
    post = await PostService.create_post(db, post_data, current_user.id)
    return post

@router.get("/", response_model=List[schemas.PostResponse])
async def get_posts(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get user's posts"""
    posts = await PostCRUD.get_posts_by_user(db, current_user.id, skip, limit, status)
    return posts

@router.get("/{post_id}", response_model=schemas.PostResponse)
async def get_post(
    post_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get a specific post"""
    post = await PostCRUD.get_post_by_id(db, post_id, current_user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.put("/{post_id}", response_model=schemas.PostResponse)
async def update_post(
    post_id: int,
    post_update: schemas.PostUpdate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Update a post"""
    post = await PostCRUD.update_post(db, post_id, current_user.id, post_update)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.post("/{post_id}/publish")
async def publish_post(
    post_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Publish a post immediately"""
    post = await PostCRUD.get_post_by_id(db, post_id, current_user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    from ..tasks.scheduled_tasks import publish_post_task
    publish_post_task.delay(post_id)
    
    return {"message": "Post is being published"}

@router.post("/enhance")
async def enhance_content(
    request: schemas.ContentEnhancementRequest,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """Enhance content for different platforms using AI"""
    enhancements = []
    
    for platform in request.platforms:
        enhanced_content = await ai_service.enhance_content(
            content=request.content,
            platform=platform,
            image_count=request.image_count,
            tone=request.tone
        )
        enhancements.append({
            "platform": platform,
            "enhanced_content": enhanced_content
        })
    
    return {"enhancements": enhancements}

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """Transcribe audio file to text"""
    # Upload audio file
    audio_file_url = await PostService.upload_audio(audio, current_user.id)
    
    # Transcribe audio
    transcription = await PostService.transcribe_audio(audio_file_url)
    
    return {"transcription": transcription}

@router.get("/calendar/events")
async def get_calendar_events(
    start_date: str,
    end_date: str,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get posts for calendar view"""
    events = await PostService.get_calendar_events(db, current_user.id, start_date, end_date)
    return {"events": events}