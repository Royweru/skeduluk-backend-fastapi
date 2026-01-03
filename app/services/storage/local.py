# app/services/storage/local.py
import aiofiles
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import UploadFile
import uuid
import os

from .base import StorageProvider
from ...config import settings

class LocalStorageProvider(StorageProvider):
    """Local filesystem storage for development"""
    
    def __init__(self):
        self.base_path = Path(settings.UPLOAD_DIR)
        self.base_path.mkdir(parents=True, exist_ok=True)
        (self.base_path / "images").mkdir(exist_ok=True)
        (self.base_path / "videos").mkdir(exist_ok=True)
        (self.base_path / "audio").mkdir(exist_ok=True)
    
    async def upload_file(
        self, 
        file: UploadFile, 
        user_id: int, 
        file_type: str = "image",
        custom_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Save file to local filesystem"""
        await file.seek(0)
        
        ext = Path(file.filename).suffix.lower()
        if custom_filename:
            filename = f"{user_id}/{file_type}/{custom_filename}{ext}"
        else:
            filename = f"{user_id}/{file_type}/{uuid.uuid4()}{ext}"
        
        file_path = self.base_path / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = await file.read()
        
        async with aiofiles.open(file_path, 'wb') as out_file:
            await out_file.write(content)
        
        url = f"{settings.BACKEND_URL}/uploads/{filename}"
        
        return {
            "url": url,
            "path": str(file_path),
            "filename": file.filename,
            "size": len(content),
            "type": file_type
        }
    
    async def delete_file(self, file_url: str) -> bool:
        """Delete local file"""
        try:
            path_part = file_url.split("/uploads/")[1]
            file_path = self.base_path / path_part
            
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception as e:
            print(f"Local delete error: {e}")
            return False
    
    def get_public_url(self, resource_path: str) -> str:
        return f"{settings.BACKEND_URL}/uploads/{resource_path}"
    
    async def download_file(self, file_url: str) -> Optional[bytes]:
        """Download from local storage"""
        try:
            path_part = file_url.split("/uploads/")[1]
            file_path = self.base_path / path_part
            
            if not file_path.exists():
                return None
            
            async with aiofiles.open(file_path, 'rb') as f:
                return await f.read()
        except Exception as e:
            print(f"Local download error: {e}")
            return None