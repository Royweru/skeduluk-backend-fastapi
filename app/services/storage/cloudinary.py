# app/services/storage/cloudinary.py
"""
Cloudinary Storage Provider - integrates with your existing storage abstraction layer
"""
import cloudinary
import cloudinary.uploader
import traceback
from io import BytesIO
from typing import Optional, Dict, Any, BinaryIO
from fastapi import UploadFile, HTTPException
from ...config import settings


class CloudinaryStorageProvider:
    """Storage provider for Cloudinary"""
    
    def __init__(self):
        """Initialize Cloudinary configuration"""
        if not settings.CLOUDINARY_CLOUD_NAME:
            raise ValueError("CLOUDINARY_CLOUD_NAME not configured")
        
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True
        )
        
        print(f"✅ Cloudinary Storage Provider initialized: {settings.CLOUDINARY_CLOUD_NAME}")
    
    async def upload_file(
        self,
        file: UploadFile,
        folder: str,
        filename: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Upload a file to Cloudinary
        
        Args:
            file: The uploaded file
            folder: Folder path in Cloudinary (e.g., "skeduluk/images/123")
            filename: Optional custom filename
            **kwargs: Additional options (resource_type, etc.)
        
        Returns:
            Secure URL of the uploaded file
        """
        try:
            # Read file content
            file.file.seek(0)
            file_content = await file.read()
            
            # Determine resource type
            resource_type = kwargs.get('resource_type', 'auto')
            if not resource_type or resource_type == 'auto':
                if file.content_type.startswith('video/'):
                    resource_type = 'video'
                elif file.content_type.startswith('image/'):
                    resource_type = 'image'
                elif file.content_type.startswith('audio/'):
                    resource_type = 'video'  # Audio uses 'video' in Cloudinary
                else:
                    resource_type = 'raw'
            
            # Upload options
            upload_options = {
                'folder': folder,
                'resource_type': resource_type,
                'use_filename': True,
                'unique_filename': True,
                'overwrite': False
            }
            
            # Add custom filename if provided
            if filename:
                upload_options['public_id'] = f"{folder}/{filename}"
            
            # For images, add optimization
            if resource_type == 'image':
                upload_options['quality'] = 'auto:good'
                upload_options['fetch_format'] = 'auto'
            
            # Upload to Cloudinary
            # Use chunked upload for large files (>100MB)
            file_size_mb = len(file_content) / (1024 * 1024)
            
            if file_size_mb > 100 and resource_type == 'video':
                print(f"📹 Large file ({file_size_mb:.2f}MB), using chunked upload...")
                result = cloudinary.uploader.upload_large(
                    file_content,
                    **upload_options,
                    chunk_size=20 * 1024 * 1024  # 20MB chunks
                )
            else:
                result = cloudinary.uploader.upload(
                    file_content,
                    **upload_options
                )
            
            secure_url = result['secure_url']
            print(f"✅ Uploaded to Cloudinary: {secure_url}")
            
            return secure_url
            
        except Exception as e:
            print(f"❌ Cloudinary upload error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload to Cloudinary: {str(e)}"
            )
    
    async def delete_file(self, file_url: str) -> bool:
        """
        Delete a file from Cloudinary
        
        Args:
            file_url: The full Cloudinary URL or public_id
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract public_id from URL
            # https://res.cloudinary.com/cloud/image/upload/v123/folder/file.jpg
            # -> folder/file
            
            if file_url.startswith('http'):
                # Extract from URL
                parts = file_url.split('/upload/')
                if len(parts) == 2:
                    public_id = parts[1].split('.')[0]  # Remove extension
                    # Remove version if present
                    if '/' in public_id and public_id.split('/')[0].startswith('v'):
                        public_id = '/'.join(public_id.split('/')[1:])
                else:
                    return False
            else:
                # Assume it's already a public_id
                public_id = file_url
            
            # Determine resource type from URL
            resource_type = 'image'
            if '/video/' in file_url:
                resource_type = 'video'
            elif '/raw/' in file_url:
                resource_type = 'raw'
            
            # Delete from Cloudinary
            result = cloudinary.uploader.destroy(
                public_id,
                resource_type=resource_type
            )
            
            if result.get('result') == 'ok':
                print(f"✅ Deleted from Cloudinary: {public_id}")
                return True
            else:
                print(f"⚠️ Failed to delete: {result}")
                return False
                
        except Exception as e:
            print(f"❌ Cloudinary delete error: {e}")
            return False
    
    async def get_file_url(self, file_path: str) -> str:
        """
        Get the public URL for a file
        
        Args:
            file_path: The file path or public_id
        
        Returns:
            The public URL
        """
        # If already a full URL, return as is
        if file_path.startswith('http'):
            return file_path
        
        # Otherwise, construct the URL
        # This assumes the file_path is a public_id
        return f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}/image/upload/{file_path}"
    
    def get_upload_url(self, **kwargs) -> str:
        """
        Get a pre-signed upload URL (if needed for client-side uploads)
        Not commonly used with Cloudinary
        """
        # Cloudinary handles this differently - you'd use the upload API
        raise NotImplementedError("Use direct upload via upload_file method")


# Convenience functions to maintain compatibility with existing code
async def upload_to_cloudinary(
    file: UploadFile,
    user_id: int,
    file_type: str = 'images'
) -> str:
    """
    Quick upload function that matches your existing API
    
    Args:
        file: The uploaded file
        user_id: User ID for organizing files
        file_type: 'images', 'videos', or 'audio'
    
    Returns:
        Secure URL of uploaded file
    """
    try:
        provider = CloudinaryStorageProvider()
        folder = f"skeduluk/{file_type}/{user_id}"
        
        return await provider.upload_file(file, folder)
    except Exception as e:
        print(f"❌ upload_to_cloudinary error: {e}")
        traceback.print_exc()
        raise