# app/services/post_service.py
import os
import uuid
import boto3
import aiofiles
from typing import List, Optional, Dict, Any
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pathlib import Path
import mimetypes

from .. import crud, models, schemas
from ..config import settings
from ..services.transcription_service import TranscriptionService

class PostService:
    # Allowed file types
    ALLOWED_IMAGE_TYPES = {
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
        'image/webp', 'image/heic', 'image/heif'
    }
    ALLOWED_VIDEO_TYPES = {
        'video/mp4', 'video/quicktime', 'video/x-msvideo', 
        'video/webm', 'video/mpeg', 'video/x-matroska'
    }
    
    # Size limits (in bytes)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
    
    # Platform-specific limits
    PLATFORM_LIMITS = {
        'twitter': {
            'max_images': 4,
            'max_videos': 1,
            'video_duration': 140  # seconds
        },
        'facebook': {
            'max_images': 10,
            'max_videos': 1,
            'video_duration': 240
        },
        'instagram': {
            'max_images': 10,
            'max_videos': 1,
            'video_duration': 60
        },
        'linkedin': {
            'max_images': 9,
            'max_videos': 1,
            'video_duration': 600
        },
        'tiktok': {
            'max_images': 0,
            'max_videos': 1,
            'video_duration': 180
        },
        'youtube': {
            'max_images': 0,
            'max_videos': 1,
            'video_duration': 3600
        }
    }

    @staticmethod
    async def create_post(
        db: AsyncSession, 
        post_data: schemas.PostCreate, 
        user_id: int,
        platform_specific_content: Optional[Dict[str, Any]] = None
    ) -> models.Post:
        """Create a new post with support for platform-specific content"""
        # Check user's plan limits
        user = await crud.UserCRUD.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("User not found")
        
        if user.posts_used >= user.posts_limit:
            raise ValueError("Post limit reached for your current plan")
        
        # Create post with platform-specific content
        post = await crud.PostCRUD.create_post(
            db, 
            post_data, 
            user_id,
            platform_specific_content=platform_specific_content
        )
        
        # If not scheduled, publish immediately
        if not post.scheduled_for:
            from ..tasks.scheduled_tasks import publish_post_task
            publish_post_task.delay(post.id)
        
        return post
    
    @staticmethod
    async def validate_media_file(
        file: UploadFile,
        allowed_types: set,
        max_size: int
    ) -> bool:
        """Validate media file type and size"""
        # Check content type
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"File type {file.content_type} not allowed"
            )
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size {file_size} exceeds maximum {max_size}"
            )
        
        return True
    
    @staticmethod
    async def upload_media(
        files: List[UploadFile], 
        user_id: int,
        platform: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Upload media files (images and videos) and return URLs with metadata
        Returns: [{"url": "...", "type": "image|video", "filename": "..."}]
        """
        media_data = []
        
        # Use local storage for development, S3 for production
        use_s3 = settings.USE_S3_STORAGE if hasattr(settings, 'USE_S3_STORAGE') else False
        
        for file in files:
            # Determine file type
            is_image = file.content_type in PostService.ALLOWED_IMAGE_TYPES
            is_video = file.content_type in PostService.ALLOWED_VIDEO_TYPES
            
            if not (is_image or is_video):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file.content_type}"
                )
            
            # Validate file
            max_size = PostService.MAX_IMAGE_SIZE if is_image else PostService.MAX_VIDEO_SIZE
            allowed_types = PostService.ALLOWED_IMAGE_TYPES if is_image else PostService.ALLOWED_VIDEO_TYPES
            await PostService.validate_media_file(file, allowed_types, max_size)
            
            # Validate against platform limits
            if platform:
                limits = PostService.PLATFORM_LIMITS.get(platform, {})
                if is_video and limits.get('max_videos', 1) == 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"{platform} does not support video uploads"
                    )
            
            # Generate unique filename
            file_extension = os.path.splitext(file.filename)[1]
            file_type = 'videos' if is_video else 'images'
            unique_filename = f"{user_id}/{file_type}/{uuid.uuid4()}{file_extension}"
            
            if use_s3:
                # Upload to S3
                file_url = await PostService._upload_to_s3(
                    file, 
                    unique_filename,
                    file.content_type
                )
            else:
                # Upload to local storage
                file_url = await PostService._upload_to_local(
                    file, 
                    unique_filename
                )
            
            media_data.append({
                "url": file_url,
                "type": "video" if is_video else "image",
                "filename": file.filename,
                "content_type": file.content_type
            })
        
        return media_data
    
    @staticmethod
    async def _upload_to_s3(
        file: UploadFile, 
        filename: str, 
        content_type: str
    ) -> str:
        """Upload file to AWS S3"""
        try:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            
            # Upload file
            s3_client.upload_fileobj(
                file.file,
                settings.AWS_BUCKET_NAME,
                filename,
                ExtraArgs={"ContentType": content_type}
            )
            
            # Generate public URL
            file_url = f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{filename}"
            return file_url
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload to S3: {str(e)}"
            )
    
    @staticmethod
    async def _upload_to_local(file: UploadFile, filename: str) -> str:
        """Upload file to local storage"""
        try:
            # Create upload directory if it doesn't exist
            upload_dir = Path(settings.UPLOAD_DIR)
            file_path = upload_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)
            
            # Generate URL (assuming backend serves files from /uploads)
            file_url = f"{settings.BACKEND_URL}/uploads/{filename}"
            return file_url
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save file: {str(e)}"
            )
    
    @staticmethod
    async def upload_images(images: List[UploadFile], user_id: int) -> List[str]:
        """Upload image files and return URLs (backward compatibility)"""
        media_data = await PostService.upload_media(images, user_id)
        return [item["url"] for item in media_data if item["type"] == "image"]
    
    @staticmethod
    async def upload_videos(videos: List[UploadFile], user_id: int) -> List[str]:
        """Upload video files and return URLs"""
        media_data = await PostService.upload_media(videos, user_id)
        return [item["url"] for item in media_data if item["type"] == "video"]
    
    @staticmethod
    async def upload_audio(audio: UploadFile, user_id: int) -> str:
        """Upload audio file and return URL"""
        # Validate audio file
        if not audio.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=400,
                detail="File must be an audio file"
            )
        
        # Generate unique filename
        file_extension = os.path.splitext(audio.filename)[1]
        unique_filename = f"{user_id}/audio/{uuid.uuid4()}{file_extension}"
        
        use_s3 = settings.USE_S3_STORAGE if hasattr(settings, 'USE_S3_STORAGE') else False
        
        if use_s3:
            return await PostService._upload_to_s3(audio, unique_filename, audio.content_type)
        else:
            return await PostService._upload_to_local(audio, unique_filename)
    
    @staticmethod
    async def transcribe_audio(audio_file_url: str) -> Optional[str]:
        """Transcribe audio file to text"""
        return await TranscriptionService.transcribe(audio_file_url)
    
    @staticmethod
    async def validate_platform_specific_content(
        content: Dict[str, Any],
        platforms: List[str]
    ) -> bool:
        """Validate platform-specific content structure"""
        for platform in platforms:
            if platform not in content:
                continue
            
            platform_content = content[platform]
            
            # Validate required fields
            if 'text' not in platform_content:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing 'text' field for platform {platform}"
                )
            
            # Validate media count
            media = platform_content.get('media', [])
            limits = PostService.PLATFORM_LIMITS.get(platform, {})
            
            images = [m for m in media if m.get('type') == 'image']
            videos = [m for m in media if m.get('type') == 'video']
            
            max_images = limits.get('max_images', 10)
            max_videos = limits.get('max_videos', 1)
            
            if len(images) > max_images:
                raise HTTPException(
                    status_code=400,
                    detail=f"{platform} allows maximum {max_images} images, got {len(images)}"
                )
            
            if len(videos) > max_videos:
                raise HTTPException(
                    status_code=400,
                    detail=f"{platform} allows maximum {max_videos} video, got {len(videos)}"
                )
        
        return True
    
    @staticmethod
    async def get_calendar_events(
        db: AsyncSession, 
        user_id: int, 
        start_date: str, 
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Get posts for calendar view"""
        from datetime import datetime
        
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        posts = await db.execute(
            select(models.Post).where(
                and_(
                    models.Post.user_id == user_id,
                    models.Post.scheduled_for >= start,
                    models.Post.scheduled_for <= end
                )
            )
        )
        
        events = []
        for post in posts.scalars().all():
            events.append({
                "id": post.id,
                "title": post.original_content[:50] + "..." if len(post.original_content) > 50 else post.original_content,
                "start": post.scheduled_for.isoformat() if post.scheduled_for else post.created_at.isoformat(),
                "end": post.scheduled_for.isoformat() if post.scheduled_for else post.created_at.isoformat(),
                "platforms": post.platforms,
                "status": post.status,
                "has_video": bool(post.platform_specific_content and any(
                    any(m.get('type') == 'video' for m in pc.get('media', []))
                    for pc in post.platform_specific_content.values()
                ))
            })
        
        return events
    
    @staticmethod
    async def get_media_stats(db: AsyncSession, user_id: int) -> Dict[str, Any]:
        """Get media upload statistics for user"""
        posts = await db.execute(
            select(models.Post).where(models.Post.user_id == user_id)
        )
        
        total_images = 0
        total_videos = 0
        total_size = 0
        
        for post in posts.scalars().all():
            if post.platform_specific_content:
                for platform_content in post.platform_specific_content.values():
                    media = platform_content.get('media', [])
                    for item in media:
                        if item.get('type') == 'image':
                            total_images += 1
                        elif item.get('type') == 'video':
                            total_videos += 1
        
        return {
            "total_images": total_images,
            "total_videos": total_videos,
            "total_media": total_images + total_videos
        }