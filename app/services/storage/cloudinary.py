"""
Cloudinary Storage Provider
DEV-ONLY implementation for public image & video URLs
"""

import cloudinary
import cloudinary.uploader
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

    async def upload_file(
        self,
        file: UploadFile,
        folder: str
    ) -> str:
        """
        Upload image or video and return a public HTTPS URL
        """

        try:
            file.file.seek(0)

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

            result = cloudinary.uploader.upload(
                file.file,
                folder=folder,
                resource_type=resource_type,
                use_filename=True,
                unique_filename=True,
                overwrite=False
            )

            return result["secure_url"]

        except HTTPException:
            raise
        except Exception as e:
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
    provider = CloudinaryStorageProvider()
    folder = f"skeduluk/{file_type}/{user_id}"
    return await provider.upload_file(file, folder)
