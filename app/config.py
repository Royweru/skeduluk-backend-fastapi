from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # JWT
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # File Storage
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_BUCKET_NAME: str
    AWS_REGION: str = "us-east-1"
    
    # AI Services
    OPENAI_API_KEY: str
    
    # Social Platform APIs - Twitter/X
    TWITTER_API_KEY: str
    TWITTER_API_SECRET: str
    TWITTER_BEARER_TOKEN: str
    TWITTER_CLIENT_ID: str  # Added this - was missing
    TWITTER_CLIENT_SECRET: str  # Added this - was missing
    
    # Facebook
    FACEBOOK_APP_ID: str
    FACEBOOK_APP_SECRET: str
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    
    # LinkedIn
    LINKEDIN_CLIENT_ID: str
    LINKEDIN_CLIENT_SECRET: str
    
    # Payment (Flutterwave)
    FLUTTERWAVE_SECRET_KEY: str
    FLUTTERWAVE_PUBLIC_KEY: str
    FLUTTERWAVE_ENCRYPTION_KEY: str
    
    # SMTP/Email Configuration
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    FROM_EMAIL: str = "noreply@socialscheduler.com"
    FROM_NAME: str = "Skeduluk"
    
    # Application
    ALLOWED_ORIGINS: List[str] = [
        "https://skeduluk-social.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001"
    ]
    APP_NAME: str = "Skeduluk"
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # This will ignore extra fields instead of raising errors

settings = Settings()