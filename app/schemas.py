# app/schemas.py
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str
    
    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None

class UserResponse(UserBase):
    id: int
    plan: str
    trial_ends_at: Optional[datetime] = None
    posts_used: int
    posts_limit: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Authentication schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Social Connection schemas
class SocialConnectionBase(BaseModel):
    platform: str
    platform_user_id: str
    username: str

class SocialConnectionResponse(SocialConnectionBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Post schemas
class PostBase(BaseModel):
    original_content: str
    platforms: List[str]
    scheduled_for: Optional[datetime] = None

class PostCreate(PostBase):
    enhanced_content: Optional[Dict[str, str]] = None
    image_urls: Optional[List[str]] = None
    video_urls: Optional[List[str]] = None
    platform_specific_content: Optional[Dict[str, str]] = None
    audio_file_url: Optional[str] = None

class PostUpdate(BaseModel):
    original_content: Optional[str] = None
    platforms: Optional[List[str]] = None
    scheduled_for: Optional[datetime] = None
    enhanced_content: Optional[Dict[str, str]] = None

class PostResponse(PostBase):
    id: int
    user_id: int
    enhanced_content: Optional[Dict[str, str]] = None
    image_urls: Optional[List[str]] = None
    audio_file_url: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class PostResultBase(BaseModel):
    platform: str
    platform_post_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    posted_at: Optional[datetime] = None
    content_used: Optional[str] = None

class PostResultResponse(PostResultBase):
    id: int
    post_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Subscription schemas
class SubscriptionBase(BaseModel):
    plan: str
    amount: float
    currency: str = "USD"
    payment_method: str

class SubscriptionCreate(SubscriptionBase):
    payment_reference: Optional[str] = None

class SubscriptionResponse(SubscriptionBase):
    id: int
    user_id: int
    status: str
    payment_reference: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True

# Template schemas
class TemplateBase(BaseModel):
    name: str
    content: str
    platforms: List[str]
    is_public: bool = False

class TemplateCreate(TemplateBase):
    pass

class TemplateResponse(TemplateBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# AI Enhancement schemas
class ContentEnhancementRequest(BaseModel):
    content: str
    platforms: List[str]
    image_count: int = 0
    tone: str = "engaging"

class ContentEnhancementResponse(BaseModel):
    platform: str
    enhanced_content: str
    original_length: int
    enhanced_length: int

# Payment schemas
class PaymentInitiateRequest(BaseModel):
    plan: str
    payment_method: str

class PaymentInitiateResponse(BaseModel):
    payment_link: str
    reference: str

# Calendar schemas
class CalendarEvent(BaseModel):
    id: int
    title: str
    start: datetime
    end: datetime
    platforms: List[str]
    status: str