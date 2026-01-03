# app/services/cloudinary_service.py
import cloudinary
import cloudinary.uploader
from typing import Optional, Dict, Any
from fastapi import UploadFile, HTTPException
from ..config import settings

class CloudinaryService:
    """Service for handling media uploads to Cloudinary"""
    
    @staticmethod
    def initialize():
        """Initialize Cloudinary configuration"""
        if not settings.CLOUDINARY_CLOUD_NAME:
            raise ValueError("CLOUDINARY_CLOUD_NAME not configured")
        
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True  # Always use HTTPS
        )
        
        print(f"✅ Cloudinary initialized: {settings.CLOUDINARY_CLOUD_NAME}")
    
    @staticmethod
    async def upload_image(
        file: UploadFile,
        user_id: int,
        folder: str = "skeduluk/images"
    ) -> Dict[str, Any]:
        """
        Upload an image to Cloudinary
        
        Returns:
            {
                "url": "https://res.cloudinary.com/...",
                "public_id": "skeduluk/images/xxx",
                "secure_url": "https://res.cloudinary.com/...",
                "format": "jpg",
                "width": 1920,
                "height": 1080,
                "bytes": 123456
            }
        """
        try:
            # Initialize if not already done
            CloudinaryService.initialize()
            
            # Read file content
            file.file.seek(0)
            file_content = await file.read()
            
            # Upload to Cloudinary with auto-optimization
            result = cloudinary.uploader.upload(
                file_content,
                folder=f"{folder}/{user_id}",
                resource_type="image",
                # Auto-optimize images
                quality="auto:good",
                fetch_format="auto",
                # Generate unique filename
                use_filename=True,
                unique_filename=True,
                overwrite=False
            )
            
            print(f"✅ Image uploaded to Cloudinary: {result['secure_url']}")
            
            return {
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "secure_url": result["secure_url"],
                "format": result["format"],
                "width": result.get("width"),
                "height": result.get("height"),
                "bytes": result["bytes"]
            }
            
        except Exception as e:
            print(f"❌ Cloudinary image upload error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload image to Cloudinary: {str(e)}"
            )
    
    @staticmethod
    async def upload_video(
        file: UploadFile,
        user_id: int,
        folder: str = "skeduluk/videos"
    ) -> Dict[str, Any]:
        """
        Upload a video to Cloudinary
        
        Returns:
            {
                "url": "https://res.cloudinary.com/...",
                "public_id": "skeduluk/videos/xxx",
                "secure_url": "https://res.cloudinary.com/...",
                "format": "mp4",
                "duration": 30.5,
                "width": 1920,
                "height": 1080,
                "bytes": 5234567
            }
        """
        try:
            # Initialize if not already done
            CloudinaryService.initialize()
            
            # Read file content
            file.file.seek(0)
            file_content = await file.read()
            
            # For videos larger than 100MB, use upload_large
            if len(file_content) > 100 * 1024 * 1024:
                print(f"📹 Large video detected ({len(file_content) / 1024 / 1024:.2f}MB), using chunked upload...")
                result = cloudinary.uploader.upload_large(
                    file_content,
                    folder=f"{folder}/{user_id}",
                    resource_type="video",
                    chunk_size=20 * 1024 * 1024,  # 20MB chunks
                    use_filename=True,
                    unique_filename=True,
                    overwrite=False
                )
            else:
                # Regular upload for smaller videos
                result = cloudinary.uploader.upload(
                    file_content,
                    folder=f"{folder}/{user_id}",
                    resource_type="video",
                    use_filename=True,
                    unique_filename=True,
                    overwrite=False
                )
            
            print(f"✅ Video uploaded to Cloudinary: {result['secure_url']}")
            
            return {
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "secure_url": result["secure_url"],
                "format": result["format"],
                "duration": result.get("duration"),
                "width": result.get("width"),
                "height": result.get("height"),
                "bytes": result["bytes"]
            }
            
        except Exception as e:
            print(f"❌ Cloudinary video upload error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload video to Cloudinary: {str(e)}"
            )
    
    @staticmethod
    async def upload_audio(
        file: UploadFile,
        user_id: int,
        folder: str = "skeduluk/audio"
    ) -> Dict[str, Any]:
        """Upload an audio file to Cloudinary"""
        try:
            CloudinaryService.initialize()
            
            file.file.seek(0)
            file_content = await file.read()
            
            result = cloudinary.uploader.upload(
                file_content,
                folder=f"{folder}/{user_id}",
                resource_type="video",  # Audio uses 'video' resource type
                use_filename=True,
                unique_filename=True,
                overwrite=False
            )
            
            print(f"✅ Audio uploaded to Cloudinary: {result['secure_url']}")
            
            return {
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "secure_url": result["secure_url"],
                "format": result["format"],
                "duration": result.get("duration"),
                "bytes": result["bytes"]
            }
            
        except Exception as e:
            print(f"❌ Cloudinary audio upload error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload audio to Cloudinary: {str(e)}"
            )
    
    @staticmethod
    def delete_file(public_id: str, resource_type: str = "image") -> bool:
        """
        Delete a file from Cloudinary
        
        Args:
            public_id: The public ID of the file (e.g., "skeduluk/images/123/abc123")
            resource_type: "image", "video", or "raw"
        
        Returns:
            True if successful, False otherwise
        """
        try:
            CloudinaryService.initialize()
            
            result = cloudinary.uploader.destroy(
                public_id,
                resource_type=resource_type
            )
            
            if result.get("result") == "ok":
                print(f"✅ Deleted from Cloudinary: {public_id}")
                return True
            else:
                print(f"⚠️ Failed to delete from Cloudinary: {result}")
                return False
                
        except Exception as e:
            print(f"❌ Cloudinary delete error: {e}")
            return False
    
    @staticmethod
    def get_video_thumbnail(video_url: str) -> str:
        """
        Generate a thumbnail URL for a video
        
        Args:
            video_url: The Cloudinary video URL
        
        Returns:
            Thumbnail image URL
        """
        # Extract public_id from URL
        # https://res.cloudinary.com/cloud_name/video/upload/v123/folder/file.mp4
        # -> folder/file
        
        parts = video_url.split('/upload/')
        if len(parts) == 2:
            public_id = parts[1].split('.')[0]  # Remove extension
            # Remove version number if present
            if public_id.startswith('v'):
                public_id = '/'.join(public_id.split('/')[1:])
            
            # Generate thumbnail URL
            return f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}/video/upload/so_0,w_400,h_300,c_fill/{public_id}.jpg"
        
        return video_url