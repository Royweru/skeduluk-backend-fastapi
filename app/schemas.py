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
    platform_specific_content: Optional[Dict[str, str]] = None
    image_urls: Optional[List[str]] = None
    video_urls: Optional[List[str]] = None 
    audio_file_url:Optional[str] 

class PostResponse(PostBase):
    id: int
    user_id: int
    enhanced_content: Optional[Dict[str, str]] = None
    image_urls: Optional[List[str]] = None
    video_urls: Optional[List[str]] = None
    audio_file_url: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    @field_validator('platforms', 'image_urls', 'video_urls', mode='before')
    @classmethod
    def parse_json_list_fields(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v
    
    @field_validator('enhanced_content', mode='before')
    @classmethod
    def parse_json_dict_fields(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
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


# ============================================================================
# TEMPLATE SCHEMAS
# ============================================================================

class TemplateVariableDefinition(BaseModel):
    name: str = Field(..., description="Variable name without braces, e.g., 'product_name'")
    label: str = Field(..., description="Human-readable label")
    type: str = Field(default="text", description="text, date, number, hashtags, url")
    placeholder: str = Field(..., description="Placeholder text")
    required: bool = Field(default=True)
    default_value: Optional[str] = None

class TemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: str
    content_template: str = Field(..., min_length=1)
    variables: Optional[List[TemplateVariableDefinition]] = None
    platform_variations: Optional[Dict[str, str]] = None
    supported_platforms: List[str] = Field(..., min_items=1)
    tone: str = Field(default="engaging")
    suggested_hashtags: Optional[List[str]] = None
    suggested_media_type: Optional[str] = None
    is_public: bool = Field(default=False)
    thumbnail_url: Optional[str] = None
    color_scheme: str = Field(default="#3B82F6")
    icon: str = Field(default="sparkles")

class TemplateCreate(TemplateBase):
    pass

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content_template: Optional[str] = None
    variables: Optional[List[TemplateVariableDefinition]] = None
    platform_variations: Optional[Dict[str, str]] = None
    is_favorite: Optional[bool] = None
    folder_id: Optional[int] = None

class TemplateResponse(TemplateBase):
    id: int
    user_id: Optional[int] = None
    is_system: bool
    is_favorite: bool
    usage_count: int
    success_rate: int
    avg_engagement: Optional[Dict[str, int]] = None
    folder_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class TemplateUseRequest(BaseModel):
    template_id: int
    variable_values: Optional[Dict[str, str]] = Field(default={}, description="Key-value pairs for variables")
    platforms: List[str] = Field(..., min_items=1)
    scheduled_for: Optional[datetime] = None
    use_ai_enhancement: bool = Field(default=False)
    images: Optional[List[str]] = None
    videos: Optional[List[str]] = None

class TemplateFolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    color: str = Field(default="#6366F1")
    icon: str = Field(default="folder")

class TemplateFolderResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    color: str
    icon: str
    template_count: Optional[int] = 0
    created_at: datetime
    
    class Config:
        from_attributes = True

class TemplateSearchRequest(BaseModel):
    query: Optional[str] = None
    category: Optional[str] = None
    platforms: Optional[List[str]] = None
    tone: Optional[str] = None
    is_favorite: Optional[bool] = None
    folder_id: Optional[int] = None
    include_system: bool = Field(default=True)
    include_community: bool = Field(default=False)
    sort_by: str = Field(default="created_at", description="created_at, usage_count, success_rate, name")
    sort_order: str = Field(default="desc", description="asc or desc")
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

class TemplateAnalyticsResponse(BaseModel):
    total_uses: int
    success_rate: int
    avg_engagement_rate: int
    platform_breakdown: Dict[str, int]
    recent_posts: List[Dict[str, Any]]
    engagement_trend: List[Dict[str, Any]]
# AI Enhancement schemas
class ContentEnhancementRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000, description="Original content to enhance")
    platforms: List[str] = Field(..., min_items=1, description="List of target platforms")
    image_count: int = Field(default=0, ge=0, le=10, description="Number of images attached")
    tone: str = Field(default="engaging", description="Desired tone for the content")
    
    class Config:
        json_schema_extra = {
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

class BulkDeleteRequest(BaseModel):
    post_ids: List[int]

class BulkRescheduleRequest(BaseModel):
    post_ids: List[int]
    scheduled_for: str  # ISO datetime string

class DuplicatePostResponse(BaseModel):
    id: int
    message: str