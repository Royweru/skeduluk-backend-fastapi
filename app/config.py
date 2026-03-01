# app/config.py
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # ========== REQUIRED FIELDS ==========
    # Database - MUST be set
    DATABASE_URL: str

    # JWT - MUST be set
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # ========== OPTIONAL FIELDS WITH DEFAULTS ==========

    # Redis (Optional - only if you're using Celery)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery (Optional - only if you're using background tasks)
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    USE_CLOUDINARY: bool = False

    # File Storage (Optional - AWS S3 for production)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_BUCKET_NAME: str = ""
    AWS_REGION: str = "us-east-1"

    # AI Services (Optional - can add later)
    OPENAI_API_KEY: str = ""

    # Social Platform APIs - Twitter/X (Optional)
    TWITTER_API_KEY: str = ""
    TWITTER_API_SECRET: str = ""
    TWITTER_BEARER_TOKEN: str = ""
    TWITTER_CLIENT_ID: str = ""
    TWITTER_CLIENT_SECRET: str = ""

    # Facebook (Optional)
    FACEBOOK_APP_ID: str = ""
    FACEBOOK_APP_SECRET: str = ""

    # LinkedIn (Optional)
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""

    # Instagram (Optional)
    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""

    # TIKTOK (Optional)
    TIKTOK_CLIENT_ID: str = ""
    TIKTOK_CLIENT_SECRET: str = ""

    # Youtube
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Local storage dir path (fallback if no cloud storage)
    UPLOAD_DIR: str = "uploads/"

    # Application URLs
    FRONTEND_URL: str = "https://skeduluk-social.vercel.app"
    BACKEND_URL: str = "https://skeduluk-fastapi.onrender.com"
    APP_URL: str = "https://skeduluk-social.vercel.app"

    # Payment - Flutterwave (Optional - can add later)
    FLUTTERWAVE_SECRET_KEY: str = ""
    FLUTTERWAVE_PUBLIC_KEY: str = ""
    FLUTTERWAVE_ENCRYPTION_KEY: str = ""

    # payment - Paystack (optional)
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_SECRET_KEY: str = ""

    # SMTP/Email Configuration (Optional - can add later)
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@skeduluk.com"
    FROM_NAME: str = "Skeduluk"

    # Application
    ALLOWED_ORIGINS: List[str] = [
        "https://skeduluk-social.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ]
    APP_NAME: str = "Skeduluk"
    DEBUG: bool = False

    # Reddit API (for content fetching)
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = "Skeduluk/1.0"

    # Video Generation Settings
    VIDEO_OUTPUT_DIR: str = "videos/"
    VIDEO_TEMP_DIR: str = "temp/"
    VIDEO_MAX_DURATION: int = 180
    VIDEO_DEFAULT_ASPECT: str = "9:16"

    # TTS Settings (OpenAI)
    OPENAI_TTS_MODEL: str = "tts-1"
    OPENAI_TTS_VOICE: str = "alloy"

    # Image Generation (DALL-E)
    DALLE_MODEL: str = "dall-e-3"
    DALLE_IMAGE_SIZE: str = "1024x1024"
    DALLE_IMAGE_QUALITY: str = "standard"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
