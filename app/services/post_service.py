# app/services/post_service.py
import os
import uuid
import boto3
from typing import List, Optional, Dict, Any
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from .. import crud, models, schemas
from ..config import settings
from ..services.transcription_service import TranscriptionService

class PostService:
    @staticmethod
    async def create_post(
        db: AsyncSession, 
        post_data: schemas.PostCreate, 
        user_id: int
    ) -> models.Post:
        """Create a new post in the database"""
        # Check user's plan limits
        user = await crud.UserCRUD.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("User not found")
        
        if user.posts_used >= user.posts_limit:
            raise ValueError("Post limit reached for your current plan")
        
        # Create post
        post = await crud.PostCRUD.create_post(db, post_data, user_id)
        
        # If not scheduled, publish immediately
        if not post.scheduled_for:
            from ..tasks.scheduled_tasks import publish_post_task
            publish_post_task.delay(post.id)
        
        return post
    
    @staticmethod
    async def upload_images(images: List[UploadFile], user_id: int) -> List[str]:
        """Upload image files and return URLs"""
        image_urls = []
        
        # Initialize S3 client
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        for image in images:
            # Generate unique filename
            file_extension = os.path.splitext(image.filename)[1]
            unique_filename = f"{user_id}/images/{uuid.uuid4()}{file_extension}"
            
            # Upload file to S3
            s3_client.upload_fileobj(
                image.file,
                settings.AWS_BUCKET_NAME,
                unique_filename,
                ExtraArgs={"ContentType": image.content_type}
            )
            
            # Generate public URL
            file_url = f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{unique_filename}"
            image_urls.append(file_url)
        
        return image_urls
    
    @staticmethod
    async def upload_audio(audio: UploadFile, user_id: int) -> str:
        """Upload audio file and return URL"""
        # Generate unique filename
        file_extension = os.path.splitext(audio.filename)[1]
        unique_filename = f"{user_id}/audio/{uuid.uuid4()}{file_extension}"
        
        # Initialize S3 client
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        # Upload file to S3
        s3_client.upload_fileobj(
            audio.file,
            settings.AWS_BUCKET_NAME,
            unique_filename,
            ExtraArgs={"ContentType": audio.content_type}
        )
        
        # Generate public URL
        file_url = f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{unique_filename}"
        return file_url
    
    @staticmethod
    async def transcribe_audio(audio_file_url: str) -> Optional[str]:
        """Transcribe audio file to text"""
        return await TranscriptionService.transcribe(audio_file_url)
    
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
                "status": post.status
            })
        
        return events