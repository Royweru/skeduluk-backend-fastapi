# app/services/storage/__init__.py
"""
Storage abstraction layer
Provides a unified interface for different storage backends (Cloudinary, S3, Local)
"""

from .factory import get_storage, get_storage_provider, reset_storage_provider

__all__ = [
    'get_storage',
    'get_storage_provider',
    'reset_storage_provider'
]