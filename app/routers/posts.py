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
    enhanced_content: Optional[str] = Form(None),
    platform_specific_content: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    videos: Optional[List[UploadFile]] = File(None),
    audio: Optional[UploadFile] = File(None),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Create a post with platform-specific content support
    
    ✅ FIXED: Uploads happen BEFORE database transaction to prevent timeout
    """
    try:
        # ===================================================================
        # STEP 1: Parse and validate input (NO DATABASE YET)
        # ===================================================================
        platforms_list = json.loads(platforms) if platforms else []
        
        enhanced_content_dict = None
        if enhanced_content:
            try:
                enhanced_content_dict = json.loads(enhanced_content)
            except json.JSONDecodeError:
                raise HTTPException(400, "Invalid enhanced_content JSON")
        
        platform_specific_content_dict = None
        if platform_specific_content:
            try:
                platform_specific_content_dict = json.loads(platform_specific_content)
            except json.JSONDecodeError:
                raise HTTPException(400, "Invalid platform_specific_content JSON")
        
        # Validate platforms
        if not platforms_list or len(platforms_list) == 0:
            raise HTTPException(400, "At least one platform must be selected")
        
        # Parse scheduled date
        scheduled_datetime = None
        if scheduled_for:
            try:
                scheduled_datetime = datetime.fromisoformat(scheduled_for.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(400, "Invalid date format. Use ISO format.")
        
        # ===================================================================
        # STEP 2: Upload media files (NO DATABASE CONNECTION YET)
        # ===================================================================
        # ✅ This is the critical fix - uploads happen OUTSIDE the DB transaction
        # ✅ This prevents database connection timeouts on large uploads
        
        print(f"📤 Starting media uploads for user {current_user.id}...")
        
        # Upload images
        image_urls = []
        if images:
            try:
                print(f"📸 Uploading {len(images)} image(s)...")
                image_urls = await PostService.upload_images(images, current_user.id)
                print(f"✅ Uploaded {len(image_urls)} images")
            except Exception as e:
                print(f"❌ Image upload failed: {e}")
                raise HTTPException(500, f"Failed to upload images: {str(e)}")
        
        # Upload videos
        video_urls = []
        if videos:
            try:
                print(f"📹 Uploading {len(videos)} video(s)...")
                video_urls = await PostService.upload_videos(videos, current_user.id)
                print(f"✅ Uploaded {len(video_urls)} videos")
            except Exception as e:
                print(f"❌ Video upload failed: {e}")
                raise HTTPException(500, f"Failed to upload videos: {str(e)}")
        
        # Upload audio
        audio_file_url = None
        if audio:
            try:
                print(f"🎤 Uploading audio...")
                audio_file_url = await PostService.upload_audio(audio, current_user.id)
                
                # Transcribe audio if provided
                transcription = await PostService.transcribe_audio(audio_file_url)
                if transcription:
                    original_content = f"{original_content}\n\n[Audio transcription]: {transcription}"
                print(f"✅ Uploaded and transcribed audio")
            except Exception as e:
                print(f"⚠️ Audio processing error: {e}")
                # Don't fail the whole request if audio fails
        
        print(f"✅ All media uploads completed")
        
        # ===================================================================
        # STEP 3: Save to database (FAST - only metadata, URLs already uploaded)
        # ===================================================================
        # ✅ Database transaction is now SUPER FAST (milliseconds, not minutes)
        
        print(f"💾 Saving post to database...")
        
        post_data = schemas.PostCreate(
            original_content=original_content,
            platforms=platforms_list,
            scheduled_for=scheduled_datetime,
            enhanced_content=enhanced_content_dict,
            platform_specific_content=platform_specific_content_dict,
            image_urls=image_urls,
            video_urls=video_urls,
            audio_file_url=audio_file_url
        )
        
        # ✅ This is FAST because media is already uploaded
        post = await PostService.create_post(db, post_data, current_user.id)
        print(f"✅ Created post ID: {post.id}")
        
        # ===================================================================
        # STEP 4: Convert to response and queue for publishing
        # ===================================================================
        
        # Convert to response schema
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
        
        # Queue for publishing if not scheduled
        if not scheduled_for:
            from app.tasks.scheduled_tasks import publish_post_task
            task = publish_post_task.delay(post.id)
            print(f"📤 Queued post {post.id} for publishing. Task: {task.id}")
            
            response_data = post_response.model_dump()
            response_data["message"] = f"Post is being published to {len(platforms_list)} platform(s)"
            response_data["task_id"] = task.id
            
            return schemas.PostCreateResponse(**response_data)
        else:
            response_data = post_response.model_dump()
            response_data["message"] = f"Post scheduled for {scheduled_datetime.strftime('%B %d, %Y at %I:%M %p')}"
            
            return schemas.PostCreateResponse(**response_data)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating post: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Failed to create post: {str(e)}")


# ===================================================================
# All other endpoints remain the same
# ===================================================================

# app/routers/posts.py

@router.get("/{post_id}/status")
async def get_post_status(
    post_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get the current status of a post and its publishing results"""
    post = await PostCRUD.get_post_by_id(db, post_id, current_user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    from app.crud import PostResultCRUD
    results = await PostResultCRUD.get_results_by_post(db, post_id)
    
    # ✅ FIX: Parse platforms JSON string to array
    platforms_list = []
    if post.platforms:
        if isinstance(post.platforms, str):
            try:
                platforms_list = json.loads(post.platforms)
            except json.JSONDecodeError:
                # Fallback: split by comma if not valid JSON
                platforms_list = [p.strip() for p in post.platforms.split(',') if p.strip()]
        elif isinstance(post.platforms, list):
            platforms_list = post.platforms
        else:
            platforms_list = []
    
    return {
        "post_id": post.id,
        "status": post.status,
        "error_message": post.error_message,
        "platforms": platforms_list, 
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "scheduled_for": post.scheduled_for.isoformat() if post.scheduled_for else None,
        "results": [
            {
                "platform": r.platform,
                "status": r.status,
                "platform_post_id": r.platform_post_id,
                "error": r.error_message,
                "posted_at": r.posted_at.isoformat() if r.posted_at else None
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
    """Manually trigger publishing of a post"""
    post = await PostCRUD.get_post_by_id(db, post_id, current_user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.status in ["posting", "posted"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Post is already {post.status}"
        )
    
    from app.tasks.scheduled_tasks import publish_post_task
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
    """Get posts for calendar view within a date range"""
    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        from sqlalchemy import select, and_, or_
        
        query = select(models.Post).where(
            and_(
                models.Post.user_id == current_user.id,
                or_(
                    and_(
                        models.Post.scheduled_for.isnot(None),
                        models.Post.scheduled_for >= start,
                        models.Post.scheduled_for <= end
                    ),
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
        
        events = []
        for post in posts:
            event_date = post.scheduled_for or post.created_at
            
            platforms_list = []
            if isinstance(post.platforms, str):
                try:
                    platforms_list = json.loads(post.platforms)
                except:
                    platforms_list = [p.strip() for p in post.platforms.split(',') if p.strip()]
            
            content_preview = post.original_content[:100] + "..." if len(post.original_content) > 100 else post.original_content
            
            events.append({
                "id": post.id,
                "title": content_preview,
                "content": post.original_content,
                "start": event_date.isoformat(),
                "end": event_date.isoformat(),
                "platforms": platforms_list,
                "status": post.status,
                "image_urls": json.loads(post.image_urls) if post.image_urls else [],
                "is_scheduled": post.scheduled_for is not None,
                "scheduled_for": post.scheduled_for.isoformat() if post.scheduled_for else None,
                "created_at": post.created_at.isoformat(),
                "error_message": post.error_message,
                "color": _get_status_color(post.status),
                "allDay": False,
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
        "scheduled": "#3b82f6",
        "processing": "#f59e0b",
        "posting": "#8b5cf6",
        "posted": "#10b981",
        "failed": "#ef4444",
        "draft": "#6b7280"
    }
    return colors.get(status, "#6b7280")


@router.get("/ai-providers/info")
async def get_ai_providers(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """Get available AI providers status"""
    return ai_service.get_provider_info()