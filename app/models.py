# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
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
    post_templates = relationship("PostTemplate", back_populates="user")  # ← ADDED
    subscriptions = relationship("Subscription", back_populates="user")  # ← ADDED

class SocialConnection(Base):
    __tablename__ = "social_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    platform = Column(String, nullable=False)  # TWITTER, FACEBOOK, LINKEDIN
    platform_user_id = Column(String, nullable=False)
    username = Column(String, nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    platform_avatar_url = Column(String, nullable=True)
    platform_username = Column(String, nullable=True)
    last_synced = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    post_results = relationship("PostResult", back_populates="post", cascade="all, delete-orphan")  # ← ADDED

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


class PostTemplate(Base):
    __tablename__ = "post_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Template info
    name = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    platforms = Column(Text, nullable=False)
    is_public = Column(Boolean, default=False)
    
    # Optional fields
    description = Column(Text, nullable=True)
    tone = Column(String, nullable=True)
    default_hashtags = Column(Text, nullable=True)
    
    # Media settings
    include_image = Column(Boolean, default=False)
    image_style = Column(String, nullable=True)
    
    # Metadata
    is_favorite = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="post_templates")


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