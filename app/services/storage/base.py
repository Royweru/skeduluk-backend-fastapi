# app/services/storage/base.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from fastapi import UploadFile

class StorageProvider(ABC):
    """Abstract base class for all storage providers"""
    
    @abstractmethod
    async def upload_file(
        self, 
        file: UploadFile, 
        user_id: int, 
        file_type: str = "image",
        custom_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload a file and return metadata with URL"""
        pass
    
    @abstractmethod
    async def delete_file(self, file_url: str) -> bool:
        """Delete a file by URL"""
        pass
    
    @abstractmethod
    def get_public_url(self, resource_path: str) -> str:
        """Generate a public URL for a resource path"""
        pass
    
    @abstractmethod
    async def download_file(self, file_url: str) -> Optional[bytes]:
        """Download file content for processing (e.g., for YouTube upload)"""
        pass