# app/schemas.py
import json
from pydantic import BaseModel, EmailStr, field_validator,Field
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



#Post schemas
class PostBase(BaseModel):
    original_content: str
    platforms: List[str]
    scheduled_for: Optional[datetime] = None
 
class PostUpdate(BaseModel):
    original_content: Optional[str] = None
    platforms: Optional[List[str]] = None
    scheduled_for: Optional[datetime] = None
    enhanced_content: Optional[Dict[str, str]] = None
    image_urls: Optional[List[str]] = None
    video_urls: Optional[List[str]] = None  # Added video support
class PostCreate(PostBase) :
    enhanced_content: Optional[Dict[str, str]] = None
    image_urls: Optional[List[str]] = None
    video_urls: Optional[List[str]] = None 
    audio_file_url:Optional[str] = None 

class PostResponse(PostBase):
    id: int
    user_id: int
    enhanced_content: Optional[Dict[str, str]] = None
    image_urls: Optional[List[str]] = None
    video_urls: Optional[List[str]] = None  # Added video support
    audio_file_url: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    @field_validator('image_urls', 'video_urls', 'enhanced_content', mode='before')
    @classmethod
    def parse_json_fields(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # Default to empty list for arrays, None for objects
                return [] if 'urls' in str(cls) else None
        return v

    class Config:
        from_attributes = True


# Response schema for post creation endpoint
class PostCreateResponse(PostResponse):
    message: Optional[str] = Field(None, exclude=True)
    task_id: Optional[str] = Field(None, exclude=True)


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
    content: str = Field(..., min_length=1, max_length=10000, description="Original content to enhance")
    platforms: List[str] = Field(..., min_items=1, description="List of target platforms")
    image_count: int = Field(default=0, ge=0, le=10, description="Number of images attached")
    tone: str = Field(default="engaging", description="Desired tone for the content")
    
    class Config:
        schema_extra = {
            "example": {
                "content": "Just launched our new product!",
                "platforms": ["TWITTER", "LINKEDIN"],
                "image_count": 1,
                "tone": "professional"
            }
        }


class PlatformEnhancement(BaseModel):
    platform: str
    enhanced_content: str


class ContentEnhancementResponse(BaseModel):
    enhancements: List[PlatformEnhancement]


class HashtagsRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    count: int = Field(default=5, ge=1, le=20, description="Number of hashtags to generate")
    
    class Config:
        schema_extra = {
            "example": {
                "content": "Excited to share our latest AI-powered features!",
                "count": 5
            }
        }


class HashtagsResponse(BaseModel):
    hashtags: List[str]


class AIProvidersResponse(BaseModel):
    groq: bool
    gemini: bool
    openai: bool
    anthropic: bool
    grok: bool
    configured_provider: str


class PostTimeResponse(BaseModel):
    platform: str
    day: str
    time: str
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
    content: str
    image_urls: Optional[List[str]] = None
    is_scheduled: bool
    scheduled_for: Optional[datetime] = None
    created_at: datetime
    error_message: Optional[str] = None
    color: str
    allDay: bool

class CalendarEventResponse(BaseModel):
    events: List[CalendarEvent]
    start_date: str
    end_date: str
    total: int
