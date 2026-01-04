# app/services/storage/s3.py
import boto3
from typing import Dict, Any, Optional
from fastapi import UploadFile
import uuid
from pathlib import Path
import httpx

from .base import StorageProvider
from ...config import settings

class S3StorageProvider(StorageProvider):
    """AWS S3 storage for production"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket = settings.AWS_BUCKET_NAME
    
    async def upload_file(
        self, 
        file: UploadFile, 
        user_id: int, 
        file_type: str = "image",
        custom_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload to S3"""
        await file.seek(0)
        
        ext = Path(file.filename).suffix.lower()
        if custom_filename:
            key = f"{user_id}/{file_type}/{custom_filename}{ext}"
        else:
            key = f"{user_id}/{file_type}/{uuid.uuid4()}{ext}"
        
        content = await file.read()
        
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=file.content_type,
            ACL="public-read"
        )
        
        url = f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
        
        return {
            "url": url,
            "path": key,
            "filename": file.filename,
            "size": len(content),
            "type": file_type
        }
    
    async def delete_file(self, file_url: str) -> bool:
        """Delete from S3"""
        try:
            key = file_url.split(f"{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/")[1]
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            print(f"S3 delete error: {e}")
            return False
    
    def get_public_url(self, resource_path: str) -> str:
        return f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{resource_path}"
    
    async def download_file(self, file_url: str) -> Optional[bytes]:
        """Download from S3"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(file_url, timeout=60)
                if response.status_code == 200:
                    return response.content
                return None
        except Exception as e:
            print(f"S3 download error: {e}")
            return None