# app/services/storage/factory.py
"""
Storage factory - creates the appropriate storage provider based on configuration
"""
from typing import Optional
from ...config import settings

# Storage provider type
StorageProvider = None


def get_storage_provider():
    """
    Get the configured storage provider based on settings
    
    Returns:
        Instance of the configured storage provider (Cloudinary, S3, or Local)
    """
    global StorageProvider
    
    # Cloudinary (recommended for development)
    if getattr(settings, 'USE_CLOUDINARY', False):
        if StorageProvider is None:
            from .cloudinary import CloudinaryStorageProvider
            StorageProvider = CloudinaryStorageProvider()
            print("✅ Using Cloudinary Storage Provider")
        return StorageProvider
    
    # AWS S3 (recommended for production)
    elif getattr(settings, 'USE_S3_STORAGE', False):
        if StorageProvider is None:
            try:
                from .s3 import S3StorageProvider
                StorageProvider = S3StorageProvider()
                print("✅ Using S3 Storage Provider")
            except ImportError:
                print("⚠️ S3 storage not available, falling back to local")
                from .local import LocalStorageProvider
                StorageProvider = LocalStorageProvider()
        return StorageProvider
    
    # Local storage (fallback - not recommended for production)
    else:
        if StorageProvider is None:
            print("⚠️ No cloud storage configured, using local storage")
            print("⚠️ This will NOT work for LinkedIn/YouTube video uploads!")
            print("ℹ️ Set USE_CLOUDINARY=true in .env to fix this")
            from .local import LocalStorageProvider
            StorageProvider = LocalStorageProvider()
        return StorageProvider


def get_storage():
    """
    Convenience function to get storage provider
    Alias for get_storage_provider()
    """
    return get_storage_provider()


# Reset storage provider (useful for testing)
def reset_storage_provider():
    """Reset the cached storage provider"""
    global StorageProvider
    StorageProvider = None