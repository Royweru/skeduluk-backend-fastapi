# app/routers/posts.py
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime
import json
from app import models, schemas, auth
from app.database import get_async_db
from app.crud import PostCRUD
from app.services.ai_service import ai_service
from app.services.post_service import PostService

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("/", response_model=schemas.PostCreateResponse)
async def create_post(
    original_content: str = Form(...),
    platforms: str = Form(...),
    scheduled_for: Optional[str] = Form(None),
    enhanced_content: Optional[dict] = Form(None),
    platform_specific_content: Optional[dict] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    videos: Optional[List[UploadFile]] = File(None),
    audio: Optional[UploadFile] = File(None),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Parse JSON strings
        platforms_list = json.loads(platforms)
        enhanced_content_dict = json.loads(enhanced_content) if enhanced_content else None
        platform_specific_content_dict = json.loads(platform_specific_content) if platform_specific_content else None
        # Validate platforms
        if not platforms_list or len(platforms_list) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one platform must be selected"
            )
        
        # Handle image uploads
        image_urls = []
        if images:
            try:
                image_urls = await PostService.upload_images(images, current_user.id)
                print(f"Uploaded {len(image_urls)} images")
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload images: {str(e)}"
                )
        
        # Handle video uploads
        video_urls = []
        if videos:
            try:
                video_urls = await PostService.upload_videos(videos, current_user.id)
                print(f"Uploaded {len(video_urls)} videos")
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload videos: {str(e)}"
                )
        
        # Handle audio upload
        audio_file_url = None
        if audio:
            try:
                audio_file_url = await PostService.upload_audio(audio, current_user.id)
                # Transcribe audio if provided
                transcription = await PostService.transcribe_audio(audio_file_url)
                if transcription:
                    original_content = f"{original_content}\n\n[Audio transcription]: {transcription}"
                print(f"Uploaded and transcribed audio")
            except Exception as e:
                print(f"Audio processing error: {e}")
                # Continue without audio if it fails
        
        # Create post
        scheduled_datetime = None
        if scheduled_for:
            try:
                scheduled_datetime = datetime.fromisoformat(scheduled_for)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format. Use ISO format."
                )
        
        post_data = schemas.PostCreate(
            original_content=original_content,
            platforms=platforms_list,
            scheduled_for=scheduled_datetime,
            enhanced_content=enhanced_content_dict,
            image_urls=image_urls,
            video_urls=video_urls,
            audio_file_url=audio_file_url
        )
        
        post = await PostService.create_post(db, post_data, current_user.id)
        
        # Convert Post model to dict using model_dump() for Pydantic v2
        # First, convert to PostResponse schema
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
        
        # If no schedule, publish immediately
        if not scheduled_for:
            from app.tasks.scheduled_tasks import publish_post_task
            
            # Queue the post for immediate publishing
            task = publish_post_task.delay(post.id)
            
            print(f"Post {post.id} queued for immediate publishing. Task ID: {task.id}")
            
            # Use model_dump() instead of dict() for Pydantic v2
            response_data = post_response.model_dump()
            response_data["message"] = f"Post is being published to {len(platforms_list)} platform(s). This may take a few moments."
            response_data["task_id"] = task.id
            
            # Return as PostCreateResponse
            return schemas.PostCreateResponse(**response_data)
        else:
            # Scheduled post - use model_dump() instead of dict()
            response_data = post_response.model_dump()
            response_data["message"] = f"Post scheduled for {scheduled_datetime.strftime('%B %d, %Y at %I:%M %p')}"
            
            return schemas.PostCreateResponse(**response_data)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating post: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create post: {str(e)}"
        )

@router.get("/{post_id}/status")
async def get_post_status(
    post_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get the current status of a post and its publishing results
    """
    post = await PostCRUD.get_post_by_id(db, post_id, current_user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Get post results (individual platform statuses)
    from app.crud import PostResultCRUD
    results = await PostResultCRUD.get_results_by_post(db, post_id)
    
    return {
        "post_id": post.id,
        "status": post.status,
        "error_message": post.error_message,
        "platforms": post.platforms,
        "created_at": post.created_at,
        "scheduled_for": post.scheduled_for,
        "results": [
            {
                "platform": r.platform,
                "status": r.status,
                "platform_post_id": r.platform_post_id,
                "error": r.error_message,
                "posted_at": r.posted_at
            }
            for r in results
        ]
    }


@router.post("/{post_id}/publish")
async def publish_post_now(
    post_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Manually trigger publishing of a post (useful for drafts or failed posts)
    """
    post = await PostCRUD.get_post_by_id(db, post_id, current_user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Check if post can be published
    if post.status in ["posting", "posted"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Post is already {post.status}"
        )
    
    from app.tasks.scheduled_tasks import publish_post_task
    
    # Queue for publishing
    task = publish_post_task.delay(post_id)
    
    return {
        "message": f"Post is being published to {len(post.platforms)} platform(s)",
        "post_id": post.id,
        "task_id": task.id,
        "platforms": post.platforms
    }


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


@router.delete("/{post_id}")
async def delete_post(
    post_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Delete a post"""
    success = await PostCRUD.delete_post(db, post_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post deleted successfully"}


# AI Endpoints (keep existing)
@router.post("/enhance", response_model=schemas.ContentEnhancementResponse)
async def enhance_content(
    request: schemas.ContentEnhancementRequest,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """Enhance content for different platforms using AI"""
    try:
        valid_platforms = ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM", "TIKTOK", "YOUTUBE"]
        for platform in request.platforms:
            if platform.upper() not in valid_platforms:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid platform: {platform}"
                )
        
        provider_info = ai_service.get_provider_info()
        has_provider = any([
            provider_info["groq"],
            provider_info["gemini"],
            provider_info["openai"],
            provider_info["anthropic"],
            provider_info["grok"]
        ])
        
        if not has_provider:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No AI provider configured"
            )
        
        enhancements = []
        
        for platform in request.platforms:
            try:
                enhanced_content = await ai_service.enhance_content(
                    content=request.content,
                    platform=platform.upper(),
                    tone=request.tone,
                    image_count=request.image_count,
                    include_hashtags=True,
                    include_emojis=platform.upper() in ["INSTAGRAM", "TIKTOK"]
                )
                
                enhancements.append({
                    "platform": platform.upper(),
                    "enhanced_content": enhanced_content
                })
                
            except Exception as e:
                print(f"Error enhancing for {platform}: {str(e)}")
                basic_enhanced = await ai_service._basic_enhancement(
                    request.content,
                    platform.upper(),
                    ai_service.platform_limits.get(platform.upper(), 3000)
                )
                enhancements.append({
                    "platform": platform.upper(),
                    "enhanced_content": basic_enhanced
                })
        
        return {"enhancements": enhancements}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Content enhancement error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enhance content: {str(e)}"
        )


@router.post("/generate-hashtags", response_model=schemas.HashtagsResponse)
async def generate_hashtags(
    request: schemas.HashtagsRequest,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """Generate relevant hashtags for content"""
    try:
        hashtags = await ai_service.generate_hashtags(
            content=request.content,
            count=request.count
        )
        return {"hashtags": hashtags}
    except Exception as e:
        print(f"Hashtag generation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate hashtags: {str(e)}"
        )

@router.get("/calendar/events", response_model=schemas.CalendarEventResponse)
async def get_calendar_events(
    start_date: str,
    end_date: str,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get posts for calendar view within a date range
    Returns both scheduled and published posts for calendar visualization
    """
    try:
        # Parse dates
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Query posts within date range
        from sqlalchemy import select, and_, or_
        
        query = select(models.Post).where(
            and_(
                models.Post.user_id == current_user.id,
                or_(
                    # Scheduled posts in range
                    and_(
                        models.Post.scheduled_for.isnot(None),
                        models.Post.scheduled_for >= start,
                        models.Post.scheduled_for <= end
                    ),
                    # Published posts in range (use created_at as fallback)
                    and_(
                        models.Post.scheduled_for.is_(None),
                        models.Post.status == "posted",
                        models.Post.created_at >= start,
                        models.Post.created_at <= end
                    )
                )
            )
        ).order_by(models.Post.scheduled_for.desc(), models.Post.created_at.desc())
        
        result = await db.execute(query)
        posts = result.scalars().all()
        
        # Format for calendar
        events = []
        for post in posts:
            # Determine event date (scheduled or published date)
            event_date = post.scheduled_for or post.created_at
            
            # Parse platforms
            platforms_list = []
            if isinstance(post.platforms, str):
                try:
                    platforms_list = json.loads(post.platforms)
                except:
                    platforms_list = [p.strip() for p in post.platforms.split(',') if p.strip()]
            
            # Get platform-specific content if available
            content_preview = post.original_content[:100] + "..." if len(post.original_content) > 100 else post.original_content
            
            events.append({
                "id": post.id,
                "title": content_preview,
                "content": post.original_content,
                "start": event_date.isoformat(),
                "end": event_date.isoformat(),  # Same as start for point events
                "platforms": platforms_list,
                "status": post.status,
                "image_urls": json.loads(post.image_urls) if post.image_urls else [],
                "is_scheduled": post.scheduled_for is not None,
                "scheduled_for": post.scheduled_for.isoformat() if post.scheduled_for else None,
                "created_at": post.created_at.isoformat(),
                "error_message": post.error_message,
                # Calendar-specific fields
                "color": _get_status_color(post.status),
                "allDay": False,  # Set to True if you want day-long events
            })
        
        return {
            "events": events,
            "start_date": start_date,
            "end_date": end_date,
            "total": len(events)
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {str(e)}"
        )
    except Exception as e:
        print(f"Calendar events error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch calendar events: {str(e)}"
        )


def _get_status_color(status: str) -> str:
    """Helper to assign colors to different post statuses"""
    colors = {
        "scheduled": "#3b82f6",  # blue
        "processing": "#f59e0b",  # amber
        "posting": "#8b5cf6",    # purple
        "posted": "#10b981",     # green
        "failed": "#ef4444",     # red
        "draft": "#6b7280"       # gray
    }
    return colors.get(status, "#6b7280")
@router.get("/ai-providers/info")
async def get_ai_providers(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """Get available AI providers status"""
    return ai_service.get_provider_info()