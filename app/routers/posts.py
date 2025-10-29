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
    """
    Create a new post
    
    - If scheduled_for is provided: post will be scheduled
    - If scheduled_for is None: post will be published immediately
    """
    try:
        # Parse JSON strings
        platforms_list = json.loads(platforms)
        enhanced_content_dict = json.loads(enhanced_content) if enhanced_content else None
        
        # Validate platforms
        if not platforms_list or len(platforms_list) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one platform must be selected"
            )
        
        # Handle file uploads
        image_urls = []
        if images:
            try:
                image_urls = await PostService.upload_images(images, current_user.id)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload images: {str(e)}"
                )
        
        audio_file_url = None
        if audio:
            try:
                audio_file_url = await PostService.upload_audio(audio, current_user.id)
                # Transcribe audio if provided
                transcription = await PostService.transcribe_audio(audio_file_url)
                if transcription:
                    original_content = f"{original_content}\n\n[Audio transcription]: {transcription}"
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
            audio_file_url=audio_file_url
        )
        
        post = await PostService.create_post(db, post_data, current_user.id)
        
        # If no schedule, publish immediately
        if not scheduled_for:
            from app.tasks.scheduled_tasks import publish_post_task
            
            # Queue the post for immediate publishing
            task = publish_post_task.delay(post.id)
            
            print(f"Post {post.id} queued for immediate publishing. Task ID: {task.id}")
            
            # Return success with helpful message
            return {
                **post.__dict__,
                "_message": f"Post is being published to {len(platforms_list)} platform(s). This may take a few moments.",
                "_task_id": task.id
            }
        else:
            # Scheduled post
            return {
                **post.__dict__,
                "_message": f"Post scheduled for {scheduled_datetime.strftime('%B %d, %Y at %I:%M %p')}",
            }
    
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


@router.get("/ai-providers/info")
async def get_ai_providers(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """Get available AI providers status"""
    return ai_service.get_provider_info()