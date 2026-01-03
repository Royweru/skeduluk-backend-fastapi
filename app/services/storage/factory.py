# app/services/storage/factory.py
from typing import Optional
from ...config import settings
from .base import StorageProvider
from .local import LocalStorageProvider
from .s3 import S3StorageProvider
from .cloudinary import CloudinaryStorageProvider

def get_storage_provider() -> StorageProvider:
    """Factory to create storage provider based on configuration"""
    storage_type = settings.STORAGE_PROVIDER.lower()
    
    if storage_type == "cloudinary":
        if not settings.CLOUDINARY_CLOUD_NAME:
            raise ValueError("CLOUDINARY_CLOUD_NAME not configured. Set STORAGE_PROVIDER=local for development.")
        return CloudinaryStorageProvider()
    
    elif storage_type == "s3":
        if not settings.AWS_BUCKET_NAME:
            raise ValueError("AWS_BUCKET_NAME not configured")
        return S3StorageProvider()
    
    elif storage_type == "local":
        return LocalStorageProvider()
    
    else:
        raise ValueError(f"Unknown STORAGE_PROVIDER: {storage_type}. Use 'local', 's3', or 'cloudinary'")

# Global singleton
_storage_instance: Optional[StorageProvider] = None

def get_storage() -> StorageProvider:
    """Get or create global storage instance"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = get_storage_provider()
    return _storage_instance

def reset_storage():
    """Reset storage instance (useful for testing)"""
    global _storage_instance
    _storage_instance = None