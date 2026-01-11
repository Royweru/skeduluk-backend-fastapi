# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Enum,Float
import sqlalchemy as sa
import enum
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text
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
    posts_used = Column(Integer, server_default=text('0'))
    posts_limit = Column(Integer, server_default=text('10'))
    
    # Timestamps
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    social_connections = relationship("SocialConnection", back_populates="user", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="user", cascade="all, delete-orphan")
    post_templates = relationship("PostTemplate", back_populates="user", cascade="all, delete-orphan")  
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")  
    template_folders = relationship("TemplateFolder", back_populates="user", cascade="all, delete-orphan")
    analytics_summaries = relationship("UserAnalyticsSummary", back_populates="user", cascade="all, delete-orphan")

class SocialConnection(Base):
    __tablename__ = "social_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String, nullable=False, index=True)  # TWITTER, FACEBOOK, LINKEDIN
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
    is_active = Column(Boolean, server_default=text('TRUE'))
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=datetime.utcnow)
    
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
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_content = Column(Text, nullable=False)
    enhanced_content = Column(JSONB, nullable=True)
    image_urls = Column(Text, nullable=True)
    video_urls = Column(Text, nullable=True)
    platform_specific_content = Column(JSONB, nullable=True)
    audio_file_url = Column(String, nullable=True)
    platforms = Column(Text, nullable=False)
    status = Column(String, server_default=text("'processing'"))
    scheduled_for = Column(DateTime, nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="posts")
    post_results = relationship("PostResult", back_populates="post", cascade="all, delete-orphan")  
    analytics = relationship("PostAnalytics", back_populates="post", cascade="all, delete-orphan")
    template_analytics = relationship("TemplateAnalytics", back_populates="post", cascade="all, delete-orphan")

class PostResult(Base):
    __tablename__ = "post_results"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String, nullable=False)
    
    # Post status
    status = Column(String, server_default=text("'pending'"))
    platform_post_id = Column(String, nullable=True)
    platform_post_url = Column(String, nullable=True)
    content_used = Column(Text, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, server_default=text('0'))
    
    # Timestamps
    posted_at = Column(DateTime, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=datetime.utcnow)
    
    # Relationships
    post = relationship("Post", back_populates="post_results")

class TemplateCategory(enum.Enum):
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

class TemplateTone(enum.Enum):
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
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)  # NULL = system template
    
    # Template Info
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(Enum(TemplateCategory), nullable=False, index=True)
    
    # Content Structure
    content_template = Column(Text, nullable=False)  # Template with {variables}
    variables = Column(JSON, nullable=True)  # List of variable definitions
    
    # Platform Variations
    platform_variations = Column(JSON, nullable=True)  # Platform-specific versions
    supported_platforms = Column(JSON, nullable=False)  # ["TWITTER", "LINKEDIN"]
    
    # Metadata
    tone = Column(Enum(TemplateTone), server_default=text("'engaging'"))
    suggested_hashtags = Column(JSON, nullable=True)  # Array of hashtags
    suggested_media_type = Column(String, nullable=True)  # "image", "video", "none"
    
    # Template Settings
    is_public = Column(Boolean, server_default=text('FALSE'))  # Community templates
    is_premium = Column(Boolean, server_default=text('FALSE'))
    is_system = Column(Boolean, server_default=text('FALSE'))  # Official Skeduluk templates
    
    # Analytics
    usage_count = Column(Integer, server_default=text('0'))
    success_rate = Column(Integer, server_default=text('0'))  # Avg engagement %
    avg_engagement = Column(JSON, nullable=True)  # {likes: 0, shares: 0, comments: 0}
    
    # UI/UX
    thumbnail_url = Column(String, nullable=True)
    color_scheme = Column(String, server_default=text("'#3B82F6'"))  # Hex color
    icon = Column(String, server_default=text("'sparkles'"))  # Icon name
    
    # Favorites & Organization
    is_favorite = Column(Boolean, server_default=text('FALSE'))
    folder_id = Column(Integer, ForeignKey("template_folders.id", ondelete="SET NULL"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="post_templates")
    folder = relationship("TemplateFolder", back_populates="templates")
    template_analytics = relationship("TemplateAnalytics", back_populates="template", cascade="all, delete-orphan")

class TemplateFolder(Base):
    __tablename__ = "template_folders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String, server_default=text("'#6366F1'"))
    icon = Column(String, server_default=text("'folder'"))
    
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="template_folders")
    templates = relationship("PostTemplate", back_populates="folder", cascade="all, delete-orphan")

class TemplateAnalytics(Base):
    __tablename__ = "template_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("post_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)
    
    # Performance Metrics
    views = Column(Integer, server_default=text('0'))
    likes = Column(Integer, server_default=text('0'))
    comments = Column(Integer, server_default=text('0'))
    shares = Column(Integer, server_default=text('0'))
    engagement_rate = Column(Integer, server_default=text('0'))
    
    platform = Column(String, nullable=False)
    posted_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    
    # Relationships
    template = relationship("PostTemplate", back_populates="template_analytics")
    post = relationship("Post", back_populates="template_analytics")

class PostAnalytics(Base):
    __tablename__ = "post_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(Enum("TWITTER", "FACEBOOK", "LINKEDIN", "INSTAGRAM", "TIKTOK", "YOUTUBE", name="platform_enum", create_type=True), nullable=False, index=True)
    metrics = Column(JSONB, nullable=True)
    fetched_at = Column(DateTime, nullable=True, index=True)
    error = Column(Text, nullable=True)
    
    # Constraints
    __table_args__ = (
        sa.UniqueConstraint('post_id', 'platform', name='uq_post_platform'),
    )
    
    post = relationship("Post", back_populates="analytics")

class UserAnalyticsSummary(Base):
    __tablename__ = "user_analytics_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    period = Column(Enum("daily", "weekly", "monthly", name="period_enum", create_type=True), nullable=False, index=True)
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False)
    total_posts = Column(Integer, server_default=text('0'))
    total_engagements = Column(Integer, server_default=text('0'))
    total_impressions = Column(Integer, server_default=text('0'))
    avg_engagement_rate = Column(Float, server_default=text('0.0'))
    platform_breakdown = Column(JSONB, nullable=True)
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'period', 'start_date', name='uq_user_period_start'),
    )
    
    user = relationship("User", back_populates="analytics_summaries")

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Subscription info
    plan = Column(String, nullable=False)
    status = Column(String, server_default=text("'active'"))
    amount = Column(Integer, nullable=False)
    currency = Column(String, server_default=text("'USD'"))
    payment_method = Column(String, nullable=False)
    payment_reference = Column(String, nullable=True)
    
    # Subscription period
    starts_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    ends_at = Column(DateTime, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")