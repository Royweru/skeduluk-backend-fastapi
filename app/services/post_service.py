# app/services/post_service.py
from datetime import datetime
import json
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

from .. import  models, schemas
from ..config import settings
from ..services.transcription_service import TranscriptionService
from ..crud import user_crud 
from ..services.storage.cloudinary import upload_to_cloudinary

class PostService:
    # Allowed file types
    ALLOWED_IMAGE_TYPES = {
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
        'image/webp', 'image/heic', 'image/heif'
    }
    ALLOWED_VIDEO_TYPES = {
        'video/mp4', 'video/quicktime', 'video/x-msvideo', 
        'video/webm', 'video/mpeg', 'video/x-matroska', 'video/x-ms-wmv'
    }
    ALLOWED_AUDIO_TYPES = {
        'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg', 
        'audio/mp4', 'audio/x-m4a', 'audio/webm'
    }
    
    # Size limits (in bytes)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB
    MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25MB
    
    # Platform-specific limits
    PLATFORM_LIMITS = {
        'twitter': {'max_images': 4, 'max_videos': 1, 'video_duration': 140, 'max_video_size': 512 * 1024 * 1024},
        'facebook': {'max_images': 10, 'max_videos': 1, 'video_duration': 240, 'max_video_size': 4 * 1024 * 1024 * 1024},
        'instagram': {'max_images': 10, 'max_videos': 1, 'video_duration': 60, 'max_video_size': 100 * 1024 * 1024},
        'linkedin': {'max_images': 9, 'max_videos': 1, 'video_duration': 600, 'max_video_size': 5 * 1024 * 1024 * 1024},
        'tiktok': {'max_images': 0, 'max_videos': 1, 'video_duration': 180, 'max_video_size': 287.6 * 1024 * 1024},
        'youtube': {'max_images': 0, 'max_videos': 1, 'video_duration': 3600, 'max_video_size': 128 * 1024 * 1024 * 1024}
    }

    @staticmethod
    async def create_post(
        db: AsyncSession, 
        post: schemas.PostCreate,
        user_id: int
    ) -> models.Post:
        """Create a new post"""
        enhanced_content_str = None
        if post.enhanced_content:
            enhanced_content_str = json.dumps(post.enhanced_content)
        
        platform_specific_content_str = None
        if post.platform_specific_content:
            platform_specific_content_str = json.dumps(post.platform_specific_content)

        image_urls_str = json.dumps(post.image_urls or [])
        video_urls_str = json.dumps(post.video_urls or [])
        platforms_str = json.dumps(post.platforms)
        
        db_post = models.Post(
            user_id=user_id,
            original_content=post.original_content,
            enhanced_content=enhanced_content_str,
            platform_specific_content=platform_specific_content_str,
            image_urls=image_urls_str,
            video_urls=video_urls_str,
            platforms=platforms_str,
            audio_file_url=post.audio_file_url,
            scheduled_for=post.scheduled_for,
            status="scheduled" if post.scheduled_for else "draft",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(db_post)
        await db.commit()
        await db.refresh(db_post)
        
        await user_crud.UserCRUD.increment_post_count(db, user_id)
        
        return db_post
    
    @staticmethod
    async def validate_media_file(
        file: UploadFile,
        allowed_types: set,
        max_size: int,
        file_type_name: str = "file"
    ) -> bool:
        """Validate media file type and size"""
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"{file_type_name} type '{file.content_type}' not allowed. Allowed types: {', '.join(allowed_types)}"
            )
        return True
    
    @staticmethod
    async def upload_media(
        files: List[UploadFile], 
        user_id: int,
        platform: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Upload media files and return URLs with metadata
        ✅ Now uses Cloudinary through your storage abstraction layer
        """
        media_data = []
        
        # ✅ Check if Cloudinary is enabled
        use_cloudinary = getattr(settings, 'USE_CLOUDINARY', False)
        use_s3 = getattr(settings, 'USE_S3_STORAGE', False)
        
        for file in files:
            is_image = file.content_type in PostService.ALLOWED_IMAGE_TYPES
            is_video = file.content_type in PostService.ALLOWED_VIDEO_TYPES
            
            if not (is_image or is_video):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file.content_type}"
                )
            
            # Get file size
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)
            
            # Validate
            max_size = PostService.MAX_IMAGE_SIZE if is_image else PostService.MAX_VIDEO_SIZE
            allowed_types = PostService.ALLOWED_IMAGE_TYPES if is_image else PostService.ALLOWED_VIDEO_TYPES
            file_type_name = "Image" if is_image else "Video"
            
            await PostService.validate_media_file(file, allowed_types, file_type_name)
            
            # ✅ Upload using Cloudinary
            if use_cloudinary:
                file_type = 'images' if is_image else 'videos'
                file_url = await upload_to_cloudinary(file, user_id, file_type)
                
                media_data.append({
                    "url": file_url,
                    "type": "video" if is_video else "image",
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "size": file_size
                })
            
            # Fallback to S3
            elif use_s3:
                file_extension = os.path.splitext(file.filename)[1].lower()
                file_type = 'videos' if is_video else 'images'
                unique_filename = f"{user_id}/{file_type}/{uuid.uuid4()}{file_extension}"
                
                file_url = await PostService._upload_to_s3(file, unique_filename, file.content_type)
                
                media_data.append({
                    "url": file_url,
                    "type": "video" if is_video else "image",
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "size": file_size
                })
            
            # Fallback to local (not recommended)
            else:
                print("⚠️ WARNING: Using local storage. Videos won't work for LinkedIn/YouTube!")
                file_extension = os.path.splitext(file.filename)[1].lower()
                file_type = 'videos' if is_video else 'images'
                unique_filename = f"{user_id}/{file_type}/{uuid.uuid4()}{file_extension}"
                
                file_url = await PostService._upload_to_local(file, unique_filename)
                
                media_data.append({
                    "url": file_url,
                    "type": "video" if is_video else "image",
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "size": file_size
                })
        
        return media_data
    
    @staticmethod
    async def _upload_to_s3(file: UploadFile, filename: str, content_type: str) -> str:
        """Upload file to AWS S3"""
        try:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            
            file.file.seek(0)
            s3_client.upload_fileobj(
                file.file,
                settings.AWS_BUCKET_NAME,
                filename,
                ExtraArgs={"ContentType": content_type, "ACL": "public-read"}
            )
            
            return f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{filename}"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")
    
    @staticmethod
    async def _upload_to_local(file: UploadFile, filename: str) -> str:
        """Upload file to local storage (NOT RECOMMENDED FOR PRODUCTION)"""
        try:
            upload_dir = Path(settings.UPLOAD_DIR)
            file_path = upload_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            file.file.seek(0)
            async with aiofiles.open(file_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)
            
            LOCAL_URL = 'http://localhost:3000'
            return f"{LOCAL_URL}/uploads/{filename}"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Local upload failed: {str(e)}")
    
    @staticmethod
    async def upload_images(images: List[UploadFile], user_id: int) -> List[str]:
        """Upload images and return URLs"""
        if not images:
            return []
        
        image_files = [f for f in images if f.content_type in PostService.ALLOWED_IMAGE_TYPES]
        if not image_files:
            return []
        
        media_data = await PostService.upload_media(image_files, user_id)
        return [item["url"] for item in media_data if item["type"] == "image"]
    
    @staticmethod
    async def upload_videos(videos: List[UploadFile], user_id: int) -> List[str]:
        """Upload videos and return URLs"""
        if not videos:
            return []
        
        video_files = [f for f in videos if f.content_type in PostService.ALLOWED_VIDEO_TYPES]
        if not video_files:
            return []
        
        media_data = await PostService.upload_media(video_files, user_id)
        return [item["url"] for item in media_data if item["type"] == "video"]
    
    @staticmethod
    async def upload_audio(audio: UploadFile, user_id: int) -> str:
        """Upload audio and return URL"""
        if audio.content_type not in PostService.ALLOWED_AUDIO_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid audio type: {audio.content_type}"
            )
        
        await PostService.validate_media_file(
            audio, 
            PostService.ALLOWED_AUDIO_TYPES, 
            PostService.MAX_AUDIO_SIZE,
            "Audio"
        )
        
        use_cloudinary = getattr(settings, 'USE_CLOUDINARY', False)
        
        if use_cloudinary:
            return await upload_to_cloudinary(audio, user_id, 'audio')
        
        # Fallback
        use_s3 = getattr(settings, 'USE_S3_STORAGE', False)
        file_extension = os.path.splitext(audio.filename)[1].lower()
        unique_filename = f"{user_id}/audio/{uuid.uuid4()}{file_extension}"
        
        if use_s3:
            return await PostService._upload_to_s3(audio, unique_filename, audio.content_type)
        else:
            return await PostService._upload_to_local(audio, unique_filename)
    
    @staticmethod
    async def transcribe_audio(audio_file_url: str) -> Optional[str]:
        """Transcribe audio to text"""
        try:
            return await TranscriptionService.transcribe(audio_file_url)
        except Exception as e:
            print(f"Audio transcription error: {e}")
            return None
    
    # ... rest of your existing methods ...
    @staticmethod
    async def validate_platform_specific_content(
        content: Dict[str, Any],
        platforms: List[str]
    ) -> bool:
        """Validate platform-specific content structure"""
        for platform in platforms:
            platform_lower = platform.lower()
            
            if platform_lower not in content:
                continue
            
            platform_content = content[platform_lower]
            
            # Validate required fields
            if 'text' not in platform_content:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing 'text' field for platform {platform}"
                )
            
            # Validate media count
            media = platform_content.get('media', [])
            limits = PostService.PLATFORM_LIMITS.get(platform_lower, {})
            
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
            
            # Validate no mixing of images and videos for platforms that don't support it
            if videos and images:
                if platform_lower in ['twitter', 'instagram']:
                    raise HTTPException(
                        status_code=400,
                        detail=f"{platform} does not support mixing images and videos in the same post"
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
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
            )
        
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
            # Parse platforms from JSON string
            platforms = json.loads(post.platforms) if isinstance(post.platforms, str) else post.platforms
            
            # Parse video_urls to check for videos
            video_urls = []
            if post.video_urls:
                video_urls = json.loads(post.video_urls) if isinstance(post.video_urls, str) else post.video_urls
            
            # Check for videos in platform_specific_content
            has_video = bool(video_urls)
            if not has_video and post.platform_specific_content:
                psc = json.loads(post.platform_specific_content) if isinstance(post.platform_specific_content, str) else post.platform_specific_content
                has_video = any(
                    any(m.get('type') == 'video' for m in pc.get('media', []))
                    for pc in psc.values()
                ) if psc else False
            
            events.append({
                "id": post.id,
                "title": post.original_content[:50] + "..." if len(post.original_content) > 50 else post.original_content,
                "start": post.scheduled_for.isoformat() if post.scheduled_for else post.created_at.isoformat(),
                "end": post.scheduled_for.isoformat() if post.scheduled_for else post.created_at.isoformat(),
                "platforms": platforms,
                "status": post.status,
                "has_video": has_video,
                "has_audio": bool(post.audio_file_url)
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
        total_audio = 0
        
        for post in posts.scalars().all():
            # Count images
            if post.image_urls:
                image_urls = json.loads(post.image_urls) if isinstance(post.image_urls, str) else post.image_urls
                total_images += len(image_urls) if image_urls else 0
            
            # Count videos
            if post.video_urls:
                video_urls = json.loads(post.video_urls) if isinstance(post.video_urls, str) else post.video_urls
                total_videos += len(video_urls) if video_urls else 0
            
            # Count audio
            if post.audio_file_url:
                total_audio += 1
            
            # Count media from platform_specific_content
            if post.platform_specific_content:
                psc = json.loads(post.platform_specific_content) if isinstance(post.platform_specific_content, str) else post.platform_specific_content
                if psc:
                    for platform_content in psc.values():
                        media = platform_content.get('media', [])
                        for item in media:
                            if item.get('type') == 'image':
                                total_images += 1
                            elif item.get('type') == 'video':
                                total_videos += 1
        
        return {
            "total_images": total_images,
            "total_videos": total_videos,
            "total_audio": total_audio,
            "total_media": total_images + total_videos + total_audio
        }
    
    @staticmethod
    async def delete_media_file(file_url: str) -> bool:
        """Delete a media file from storage"""
        try:
            use_s3 = getattr(settings, 'USE_S3_STORAGE', False)
            
            if use_s3:
                # Extract filename from S3 URL
                filename = file_url.split(f"{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/")[1]
                
                s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_REGION
                )
                
                s3_client.delete_object(
                    Bucket=settings.AWS_BUCKET_NAME,
                    Key=filename
                )
            else:
                # Extract filename from local URL
                filename = file_url.split('/uploads/')[1]
                file_path = Path(settings.UPLOAD_DIR) / filename
                
                if file_path.exists():
                    file_path.unlink()
            
            return True
            
        except Exception as e:
            print(f"Error deleting media file: {e}")
            return False
    
    @staticmethod
    def get_platform_media_requirements(platform: str) -> Dict[str, Any]:
        """Get media requirements for a specific platform"""
        platform_lower = platform.lower()
        limits = PostService.PLATFORM_LIMITS.get(platform_lower, {})
        
        return {
            "platform": platform,
            "max_images": limits.get('max_images', 0),
            "max_videos": limits.get('max_videos', 0),
            "max_video_duration": limits.get('video_duration', 0),
            "max_video_size_mb": limits.get('max_video_size', 0) / (1024 * 1024),
            "supports_images": limits.get('max_images', 0) > 0,
            "supports_videos": limits.get('max_videos', 0) > 0,
            "allowed_image_types": list(PostService.ALLOWED_IMAGE_TYPES),
            "allowed_video_types": list(PostService.ALLOWED_VIDEO_TYPES)
        }