# app/routers/posts.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form,status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime
from .. import auth, schemas, models
from ..database import get_async_db
from app.services.post_service import ai_service,PostService
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

@router.post("/enhance", response_model=schemas.ContentEnhancementResponse)
async def enhance_content(
    request: schemas.ContentEnhancementRequest,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Enhance content for different platforms using AI
    
    - **content**: Original content to enhance
    - **platforms**: List of target platforms (TWITTER, LINKEDIN, FACEBOOK, INSTAGRAM)
    - **tone**: Desired tone (engaging, professional, casual, humorous, inspirational)
    - **image_count**: Number of images attached (for context)
    """
    try:
        # Validate platforms
        valid_platforms = ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"]
        for platform in request.platforms:
            if platform.upper() not in valid_platforms:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid platform: {platform}. Must be one of: {', '.join(valid_platforms)}"
                )
        
        # Check if any AI provider is available
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
                detail="No AI provider configured. Please set up GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, or XAI_API_KEY"
            )
        
        # Enhance content for each platform
        enhancements = []
        
        for platform in request.platforms:
            print(f"Enhancing content for platform: {platform}")
            
            try:
                enhanced_content = await ai_service.enhance_content(
                    content=request.content,
                    platform=platform.upper(),
                    tone=request.tone,
                    image_count=request.image_count,
                    include_hashtags=True,
                    include_emojis=platform.upper() == "INSTAGRAM"  # Auto-enable emojis for Instagram
                )
                
                enhancements.append({
                    "platform": platform.upper(),
                    "enhanced_content": enhanced_content
                })
                
            except Exception as e:
                print(f"Error enhancing for {platform}: {str(e)}")
                # Instead of failing completely, use basic enhancement
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
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enhance content: {str(e)}"
        )


@router.post("/generate-hashtags", response_model=schemas.HashtagsResponse)
async def generate_hashtags(
    request: schemas.HashtagsRequest,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Generate relevant hashtags for content
    
    - **content**: Content to generate hashtags for
    - **count**: Number of hashtags to generate (default: 5)
    """
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


@router.get("/ai-providers", response_model=schemas.AIProvidersResponse)
async def get_ai_providers(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Get information about available AI providers
    """
    return ai_service.get_provider_info()


@router.get("/suggest-post-time", response_model=schemas.PostTimeResponse)
async def suggest_post_time(
    platform: str,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Get suggested optimal posting time for a platform
    
    - **platform**: Target platform (TWITTER, LINKEDIN, FACEBOOK, INSTAGRAM)
    """
    valid_platforms = ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"]
    
    if platform.upper() not in valid_platforms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform: {platform}. Must be one of: {', '.join(valid_platforms)}"
        )
    
    suggestion = await ai_service.suggest_post_time(platform.upper())
    
    return {
        "platform": platform.upper(),
        **suggestion
    }

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