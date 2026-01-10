# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey,JSON ,Enum
import enum
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timedelta
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    # Basic info
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # Email verification
    is_email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String, nullable=True)
    email_verification_expires = Column(DateTime, nullable=True)
    
    # Password reset
    password_reset_token = Column(String, nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    
    # Account status
    is_active = Column(Boolean, default=True)
    plan = Column(String, default="trial")
    trial_ends_at = Column(DateTime, nullable=True)
    posts_used = Column(Integer, default=0)
    posts_limit = Column(Integer, default=10)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships - FIXED: Added missing relationships
    social_connections = relationship("SocialConnection", back_populates="user")
    posts = relationship("Post", back_populates="user")
    post_templates = relationship("PostTemplate", back_populates="user")  
    subscriptions = relationship("Subscription", back_populates="user")  
    template_folders = relationship("TemplateFolder", back_populates="user")
class SocialConnection(Base):
    __tablename__ = "social_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    platform = Column(String, nullable=False)  # TWITTER, FACEBOOK, LINKEDIN
    platform_user_id = Column(String, nullable=False)
    username = Column(String, nullable=False)
    protocol = Column(String, nullable=True)  # oauth1 or oauth2
    oauth_token_secret = Column(Text, nullable=True)  # For OAuth 1.0
    access_token = Column(Text, nullable=False)
    
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    platform_avatar_url = Column(String, nullable=True)
    platform_username = Column(String, nullable=True)
    last_synced = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Facebook specific fields
    facebook_page_id = Column(String, nullable=True)  # Selected page ID
    facebook_page_name = Column(String, nullable=True)  # Selected page name
    facebook_page_access_token = Column(Text, nullable=True)  # Page-specific token
    facebook_page_category = Column(String, nullable=True)
    facebook_page_picture = Column(String, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="social_connections")

class Post(Base):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_content = Column(Text, nullable=False)
    enhanced_content = Column(JSONB, nullable=True)
    image_urls = Column(Text, nullable=True)
    video_urls = Column(Text, nullable=True)
    platform_specific_content = Column(JSONB, nullable=True)
    audio_file_url = Column(String, nullable=True)
    platforms = Column(Text, nullable=False)
    status = Column(String, default="processing")
    scheduled_for = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - FIXED: Added missing post_results relationship
    user = relationship("User", back_populates="posts")
    post_results = relationship("PostResult", back_populates="post", cascade="all, delete-orphan")  
    
class PostResult(Base):
    __tablename__ = "post_results"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    platform = Column(String, nullable=False)
    
    # Post status
    status = Column(String, default="pending")
    platform_post_id = Column(String, nullable=True)
    platform_post_url = Column(String, nullable=True)
    content_used = Column(Text, nullable=True)
    
    # Engagement metrics
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Timestamps
    posted_at = Column(DateTime, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    post = relationship("Post", back_populates="post_results")


class TemplateCategory(str, enum.Enum):
    PRODUCT_LAUNCH = "product_launch"
    EVENT_PROMOTION = "event_promotion"
    BLOG_POST = "blog_post"
    ENGAGEMENT = "engagement"
    EDUCATIONAL = "educational"
    PROMOTIONAL = "promotional"
    SEASONAL = "seasonal"
    ANNOUNCEMENT = "announcement"
    BEHIND_SCENES = "behind_scenes"
    USER_GENERATED = "user_generated"
    TESTIMONIAL = "testimonial"
    INSPIRATIONAL = "inspirational"

class TemplateTone(str, enum.Enum):
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    HUMOROUS = "humorous"
    INSPIRATIONAL = "inspirational"
    EDUCATIONAL = "educational"
    URGENT = "urgent"
    FRIENDLY = "friendly"

class PostTemplate(Base):
    __tablename__ = "post_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL = system template
    
    # Template Info
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False, index=True)
    
    # Content Structure
    content_template = Column(Text, nullable=False)  # Template with {variables}
    variables = Column(JSON, nullable=True)  # List of variable definitions
    
    # Platform Variations
    platform_variations = Column(JSON, nullable=True)  # Platform-specific versions
    supported_platforms = Column(JSON, nullable=False)  # ["TWITTER", "LINKEDIN"]
    
    # Metadata
    tone = Column(String, default="engaging")
    suggested_hashtags = Column(JSON, nullable=True)  # Array of hashtags
    suggested_media_type = Column(String, nullable=True)  # "image", "video", "none"
    
    # Template Settings
    is_public = Column(Boolean, default=False)  # Community templates
    is_premium = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False)  # Official Skeduluk templates
    
    # Analytics
    usage_count = Column(Integer, default=0)
    success_rate = Column(Integer, default=0)  # Avg engagement %
    avg_engagement = Column(JSON, nullable=True)  # {likes: 0, shares: 0, comments: 0}
    
    # UI/UX
    thumbnail_url = Column(String, nullable=True)
    color_scheme = Column(String, default="#3B82F6")  # Hex color
    icon = Column(String, default="sparkles")  # Icon name
    
    # Favorites & Organization
    is_favorite = Column(Boolean, default=False)
    folder_id = Column(Integer, ForeignKey("template_folders.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="post_templates")
    folder = relationship("TemplateFolder", back_populates="templates")
    template_analytics = relationship("TemplateAnalytics", back_populates="template", cascade="all, delete-orphan")


class TemplateFolder(Base):
    __tablename__ = "template_folders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String, default="#6366F1")
    icon = Column(String, default="folder")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="template_folders")
    templates = relationship("PostTemplate", back_populates="folder")


class TemplateAnalytics(Base):
    __tablename__ = "template_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("post_templates.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    
    # Performance Metrics
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    engagement_rate = Column(Integer, default=0)
    
    platform = Column(String, nullable=False)
    posted_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    template = relationship("PostTemplate", back_populates="template_analytics")
    post = relationship("Post")


class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Subscription info
    plan = Column(String, nullable=False)
    status = Column(String, default="active")
    amount = Column(Integer, nullable=False)
    currency = Column(String, default="USD")
    payment_method = Column(String, nullable=False)
    payment_reference = Column(String, nullable=True)
    
    # Subscription period
    starts_at = Column(DateTime, default=datetime.utcnow)
    ends_at = Column(DateTime, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")