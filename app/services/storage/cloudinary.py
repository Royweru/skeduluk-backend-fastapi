"""
Cloudinary Storage Provider
PRODUCTION-READY implementation with chunked uploads for large files
"""

import cloudinary
import cloudinary.uploader
from io import BytesIO
from fastapi import UploadFile, HTTPException
from ...config import settings


class CloudinaryStorageProvider:
    def __init__(self):
        if not all([
            settings.CLOUDINARY_CLOUD_NAME,
            settings.CLOUDINARY_API_KEY,
            settings.CLOUDINARY_API_SECRET
        ]):
            raise RuntimeError("Cloudinary credentials are not fully configured")

        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True
        )
        
        print(f"✅ Cloudinary initialized: {settings.CLOUDINARY_CLOUD_NAME}")

    async def upload_file(
        self,
        file: UploadFile,
        folder: str
    ) -> str:
        """
        Upload image or video and return a public HTTPS URL
        ✅ Handles large files with chunked upload
        ✅ Uses BytesIO to avoid null byte errors
        """

        try:
            # Read file content
            file.file.seek(0)
            file_content = await file.read()
            file_size_mb = len(file_content) / (1024 * 1024)
            
            print(f"📤 Uploading {file_size_mb:.2f}MB to Cloudinary...")

            # Decide resource type (ONLY image or video)
            if file.content_type.startswith("image/"):
                resource_type = "image"
            elif file.content_type.startswith("video/"):
                resource_type = "video"
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file.content_type}"
                )

            # ✅ CRITICAL FIX: Wrap bytes in BytesIO for file-like object
            file_obj = BytesIO(file_content)
            
            # ✅ Use chunked upload for large videos (>100MB)
            if file_size_mb > 100 and resource_type == "video":
                print(f"📹 Large video detected, using chunked upload...")
                result = cloudinary.uploader.upload_large(
                    file_obj,  # ✅ File-like object, not raw file
                    folder=folder,
                    resource_type=resource_type,
                    chunk_size=20 * 1024 * 1024,  # 20MB chunks
                    use_filename=True,
                    unique_filename=True,
                    overwrite=False,
                    timeout=300  # 5 minute timeout
                )
            else:
                result = cloudinary.uploader.upload(
                    file_obj,  # ✅ File-like object, not raw file
                    folder=folder,
                    resource_type=resource_type,
                    use_filename=True,
                    unique_filename=True,
                    overwrite=False,
                    timeout=120  # 2 minute timeout
                )

            secure_url = result["secure_url"]
            print(f"✅ Uploaded to Cloudinary: {secure_url}")
            
            return secure_url

        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Cloudinary upload failed: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Cloudinary upload failed: {str(e)}"
            )


# -------------------------------------------------
# Convenience function (used by PostService)
# -------------------------------------------------

async def upload_to_cloudinary(
    file: UploadFile,
    user_id: int,
    file_type: str  # "images" or "videos"
) -> str:
    """
    Upload a file to Cloudinary
    
    Args:
        file: The file to upload
        user_id: User ID for folder organization
        file_type: "images" or "videos"
    
    Returns:
        Public HTTPS URL from Cloudinary
    """
    try:
        provider = CloudinaryStorageProvider()
        folder = f"skeduluk/{file_type}/{user_id}"
        return await provider.upload_file(file, folder)
    except Exception as e:
        print(f"❌ upload_to_cloudinary error: {e}")
        raise