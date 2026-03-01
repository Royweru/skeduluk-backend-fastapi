# app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    JSON,
    Float,
)
import sqlalchemy as sa
import enum
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text
from .database import Base


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


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    auth_provider = Column(String, nullable=True, default="email")
    last_login_method = Column(String, nullable=True)

    is_email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String, nullable=True)
    email_verification_expires = Column(DateTime, nullable=True)

    password_reset_token = Column(String, nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=True)
    plan = Column(String, default="trial")
    trial_ends_at = Column(DateTime, nullable=True)
    posts_used = Column(Integer, server_default=text("0"))
    posts_limit = Column(Integer, server_default=text("10"))

    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow
    )
    last_login = Column(DateTime, nullable=True)

    # Email notification preferences
    email_on_post_success = Column(Boolean, server_default=text("TRUE"))
    email_on_post_failure = Column(Boolean, server_default=text("TRUE"))
    email_weekly_analytics = Column(Boolean, server_default=text("TRUE"))

    # Relationships
    social_connections = relationship(
        "SocialConnection", back_populates="user", cascade="all, delete-orphan"
    )
    posts = relationship("Post", back_populates="user", cascade="all, delete-orphan")
    post_templates = relationship(
        "PostTemplate", back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )
    template_folders = relationship(
        "TemplateFolder", back_populates="user", cascade="all, delete-orphan"
    )
    analytics_summaries = relationship(
        "UserAnalyticsSummary", back_populates="user", cascade="all, delete-orphan"
    )
    content_sources = relationship(
        "ContentSource", back_populates="user", cascade="all, delete-orphan"
    )
    video_campaigns = relationship(
        "VideoCampaign", back_populates="user", cascade="all, delete-orphan"
    )
    story_contents = relationship(
        "StoryContent", back_populates="user", cascade="all, delete-orphan"
    )


class SocialConnection(Base):
    __tablename__ = "social_connections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform = Column(String, nullable=False, index=True)
    platform_user_id = Column(String, nullable=False)
    username = Column(String, nullable=False)
    protocol = Column(String, nullable=True)
    oauth_token_secret = Column(Text, nullable=True)
    access_token = Column(Text, nullable=False)

    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    platform_avatar_url = Column(String, nullable=True)
    platform_username = Column(String, nullable=True)
    last_synced = Column(DateTime, nullable=True)
    is_active = Column(Boolean, server_default=text("TRUE"))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow
    )

    facebook_page_id = Column(String, nullable=True)
    facebook_page_name = Column(String, nullable=True)
    facebook_page_access_token = Column(Text, nullable=True)
    facebook_page_category = Column(String, nullable=True)
    facebook_page_picture = Column(String, nullable=True)

    user = relationship("User", back_populates="social_connections")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
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
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="posts")
    post_results = relationship(
        "PostResult", back_populates="post", cascade="all, delete-orphan"
    )
    analytics = relationship(
        "PostAnalytics", back_populates="post", cascade="all, delete-orphan"
    )
    template_analytics = relationship(
        "TemplateAnalytics", back_populates="post", cascade="all, delete-orphan"
    )


class PostResult(Base):
    __tablename__ = "post_results"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform = Column(String, nullable=False)

    status = Column(String, server_default=text("'pending'"))
    platform_post_id = Column(String, nullable=True)
    platform_post_url = Column(String, nullable=True)
    content_used = Column(Text, nullable=True)

    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, server_default=text("0"))

    posted_at = Column(DateTime, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow
    )

    post = relationship("Post", back_populates="post_results")


class PostTemplate(Base):
    __tablename__ = "post_templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    # ✅ Changed from SAEnum to String
    category = Column(String, nullable=False, index=True)

    content_template = Column(Text, nullable=False)
    variables = Column(JSON, nullable=True)

    platform_variations = Column(JSON, nullable=True)
    supported_platforms = Column(JSON, nullable=False)

    # ✅ Changed from SAEnum to String
    tone = Column(String, server_default=text("'engaging'"))
    suggested_hashtags = Column(JSON, nullable=True)
    suggested_media_type = Column(String, nullable=True)

    is_public = Column(Boolean, server_default=text("FALSE"))
    is_premium = Column(Boolean, server_default=text("FALSE"))
    is_system = Column(Boolean, server_default=text("FALSE"))

    usage_count = Column(Integer, server_default=text("0"))
    success_rate = Column(Integer, server_default=text("0"))
    avg_engagement = Column(JSON, nullable=True)

    thumbnail_url = Column(String, nullable=True)
    color_scheme = Column(String, server_default=text("'#3B82F6'"))
    icon = Column(String, server_default=text("'sparkles'"))

    is_favorite = Column(Boolean, server_default=text("FALSE"))
    folder_id = Column(
        Integer, ForeignKey("template_folders.id", ondelete="SET NULL"), nullable=True
    )

    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow
    )
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="post_templates")
    folder = relationship("TemplateFolder", back_populates="templates")
    template_analytics = relationship(
        "TemplateAnalytics", back_populates="template", cascade="all, delete-orphan"
    )


class TemplateFolder(Base):
    __tablename__ = "template_folders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String, server_default=text("'#6366F1'"))
    icon = Column(String, server_default=text("'folder'"))

    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="template_folders")
    templates = relationship(
        "PostTemplate", back_populates="folder", cascade="all, delete-orphan"
    )


class TemplateAnalytics(Base):
    __tablename__ = "template_analytics"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(
        Integer,
        ForeignKey("post_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    post_id = Column(
        Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True
    )

    views = Column(Integer, server_default=text("0"))
    likes = Column(Integer, server_default=text("0"))
    comments = Column(Integer, server_default=text("0"))
    shares = Column(Integer, server_default=text("0"))
    engagement_rate = Column(Integer, server_default=text("0"))

    platform = Column(String, nullable=False)
    posted_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    template = relationship("PostTemplate", back_populates="template_analytics")
    post = relationship("Post", back_populates="template_analytics")


class PostAnalytics(Base):
    __tablename__ = "post_analytics"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform = Column(String, nullable=False, index=True)

    # Core metrics (common across platforms)
    views = Column(Integer, server_default=text("0"))
    impressions = Column(Integer, server_default=text("0"))
    reach = Column(Integer, server_default=text("0"))

    # Engagement metrics
    likes = Column(Integer, server_default=text("0"))
    comments = Column(Integer, server_default=text("0"))
    shares = Column(Integer, server_default=text("0"))
    saves = Column(Integer, server_default=text("0"))
    clicks = Column(Integer, server_default=text("0"))

    # Platform-specific metrics (stored as JSON)
    platform_specific_metrics = Column(JSONB, nullable=True)

    # Engagement rate calculation
    engagement_rate = Column(Float, server_default=text("0.0"))

    # Metadata
    fetched_at = Column(
        DateTime, nullable=False, index=True, server_default=text("CURRENT_TIMESTAMP")
    )
    error = Column(Text, nullable=True)

    __table_args__ = (
        sa.UniqueConstraint("post_id", "platform", name="uq_post_platform"),
    )

    post = relationship("Post", back_populates="analytics")


class UserAnalyticsSummary(Base):
    __tablename__ = "user_analytics_summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ✅ Changed from Enum to String
    period = Column(String, nullable=False, index=True)
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False)
    total_posts = Column(Integer, server_default=text("0"))
    total_engagements = Column(Integer, server_default=text("0"))
    total_impressions = Column(Integer, server_default=text("0"))
    avg_engagement_rate = Column(Float, server_default=text("0.0"))
    platform_breakdown = Column(JSONB, nullable=True)
    updated_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "user_id", "period", "start_date", name="uq_user_period_start"
        ),
    )

    user = relationship("User", back_populates="analytics_summaries")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    plan = Column(String, nullable=False)
    status = Column(String, server_default=text("'active'"))
    amount = Column(Integer, nullable=False)
    currency = Column(String, server_default=text("'USD'"))
    payment_method = Column(String, nullable=False)
    payment_reference = Column(String, nullable=True)

    starts_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    ends_at = Column(DateTime, nullable=False)

    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="subscriptions")


class ContentSource(Base):
    __tablename__ = "content_sources"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    source_type = Column(String, nullable=False)
    source_url = Column(String, nullable=True)
    subreddit_name = Column(String, nullable=True)
    rss_feed_url = Column(String, nullable=True)

    keywords_filter = Column(JSON, nullable=True)
    exclude_keywords = Column(JSON, nullable=True)
    min_score = Column(Integer, server_default=text("100"))
    max_age_hours = Column(Integer, server_default=text("24"))

    is_active = Column(Boolean, server_default=text("TRUE"))
    last_fetched = Column(DateTime, nullable=True)
    fetch_interval_hours = Column(Integer, server_default=text("6"))

    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="content_sources")
    campaigns = relationship("VideoCampaign", back_populates="content_source")


class VideoCampaign(Base):
    __tablename__ = "video_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_source_id = Column(
        Integer, ForeignKey("content_sources.id", ondelete="SET NULL"), nullable=True
    )

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    video_style = Column(String, server_default=text("'ai_images_motion'"))
    aspect_ratio = Column(String, server_default=text("'9:16'"))
    duration_seconds = Column(Integer, server_default=text("60"))

    tts_provider = Column(String, server_default=text("'openai'"))
    tts_voice = Column(String, server_default=text("'alloy'"))
    tts_speed = Column(Float, server_default=text("1.0"))

    background_music_url = Column(String, nullable=True)
    music_volume = Column(Float, server_default=text("0.3"))

    caption_style = Column(String, server_default=text("'modern'"))
    caption_font = Column(String, server_default=text("'Montserrat'"))
    caption_color = Column(String, server_default=text("'#FFFFFF'"))
    caption_position = Column(String, server_default=text("'bottom'"))

    auto_generate = Column(Boolean, server_default=text("TRUE"))
    videos_per_day = Column(Integer, server_default=text("2"))
    preferred_times = Column(JSON, nullable=True)

    platforms = Column(JSON, nullable=False)

    status = Column(String, server_default=text("'active'"))
    videos_generated = Column(Integer, server_default=text("0"))
    last_generation = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="video_campaigns")
    content_source = relationship("ContentSource", back_populates="campaigns")
    video_jobs = relationship(
        "VideoJob", back_populates="campaign", cascade="all, delete-orphan"
    )


class VideoJob(Base):
    __tablename__ = "video_jobs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(
        Integer,
        ForeignKey("video_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_url = Column(String, nullable=True)
    source_title = Column(String, nullable=True)
    source_content = Column(Text, nullable=True)

    script_text = Column(Text, nullable=True)
    script_scenes = Column(JSON, nullable=True)

    narration_url = Column(String, nullable=True)
    narration_duration = Column(Float, nullable=True)

    image_prompts = Column(JSON, nullable=True)
    image_urls = Column(JSON, nullable=True)

    video_url = Column(String, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    video_duration = Column(Float, nullable=True)

    status = Column(String, server_default=text("'pending'"))
    progress = Column(Integer, server_default=text("0"))
    error_message = Column(Text, nullable=True)

    platforms = Column(JSON, nullable=True)
    platform_post_ids = Column(JSON, nullable=True)
    posted_at = Column(DateTime, nullable=True)

    scheduled_for = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.utcnow
    )

    campaign = relationship("VideoCampaign", back_populates="video_jobs")


class StoryContent(Base):
    __tablename__ = "story_contents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id = Column(
        Integer, ForeignKey("content_sources.id", ondelete="SET NULL"), nullable=True
    )

    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    source_type = Column(String, nullable=False)
    source_url = Column(String, nullable=True)
    author = Column(String, nullable=True)

    score = Column(Integer, server_default=text("0"))
    num_comments = Column(Integer, server_default=text("0"))

    is_used = Column(Boolean, server_default=text("FALSE"))
    used_in_job_id = Column(
        Integer, ForeignKey("video_jobs.id", ondelete="SET NULL"), nullable=True
    )

    fetched_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    user = relationship("User", back_populates="story_contents")
