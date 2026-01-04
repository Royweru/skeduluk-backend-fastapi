# app/services/storage/local.py
"""
Local Storage Provider - fallback for development
WARNING: This will NOT work for LinkedIn/YouTube uploads!
"""
import os
import uuid
import aiofiles
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException
from ...config import settings


class LocalStorageProvider:
    """
    Local file system storage provider
    
    ⚠️ WARNING: Local URLs (localhost:3000) cannot be accessed by:
    - Celery workers
    - LinkedIn API
    - YouTube API
    - Any external service
    
    Use Cloudinary or S3 instead!
    """
    
    def __init__(self):
        """Initialize local storage"""
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        print(f"⚠️ Local Storage Provider initialized: {self.upload_dir}")
        print(f"⚠️ WARNING: Videos will NOT work for LinkedIn/YouTube!")
        print(f"ℹ️ Set USE_CLOUDINARY=true in .env to fix this")
    
    async def upload_file(
        self,
        file: UploadFile,
        folder: str,
        filename: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Upload a file to local storage
        
        Args:
            file: The uploaded file
            folder: Folder path (e.g., "images/123")
            filename: Optional custom filename
            **kwargs: Ignored (for compatibility)
        
        Returns:
            Local URL (WARNING: Only works on localhost!)
        """
        try:
            # Generate filename
            file_extension = os.path.splitext(file.filename)[1].lower()
            if filename:
                unique_filename = f"{folder}/{filename}{file_extension}"
            else:
                unique_filename = f"{folder}/{uuid.uuid4()}{file_extension}"
            
            # Create directory
            file_path = self.upload_dir / unique_filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save file
            file.file.seek(0)
            async with aiofiles.open(file_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)
            
            # Generate URL
            file_url = f"http://localhost:3000/uploads/{unique_filename}"
            
            print(f"⚠️ Saved to local storage: {file_url}")
            print(f"⚠️ This URL will NOT work from Celery or external APIs!")
            
            return file_url
            
        except Exception as e:
            print(f"❌ Local storage error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save file locally: {str(e)}"
            )
    
    async def delete_file(self, file_url: str) -> bool:
        """Delete a file from local storage"""
        try:
            # Extract filename from URL
            # http://localhost:3000/uploads/folder/file.jpg -> folder/file.jpg
            if '/uploads/' in file_url:
                filename = file_url.split('/uploads/')[1]
                file_path = self.upload_dir / filename
                
                if file_path.exists():
                    file_path.unlink()
                    print(f"✅ Deleted local file: {filename}")
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ Local delete error: {e}")
            return False
    
    async def get_file_url(self, file_path: str) -> str:
        """Get the URL for a local file"""
        if file_path.startswith('http'):
            return file_path
        
        return f"http://localhost:3000/uploads/{file_path}"
    
    def get_upload_url(self, **kwargs) -> str:
        """Not implemented for local storage"""
        raise NotImplementedError("Pre-signed URLs not supported for local storage")