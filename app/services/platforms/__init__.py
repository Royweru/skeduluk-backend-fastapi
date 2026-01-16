# app/services/platforms/__init__.py
"""
Platform-specific social media services.
Each platform handles its own authentication, media uploads, and posting logic.
"""

from .base_platform import BasePlatformService
from .twitter import TwitterService
from .facebook import FacebookService
from .instagram import InstagramService
from .linkedin import LinkedInService
from .youtube import YouTubeService
from .tiktok import TikTokService
__all__ = [
    "BasePlatformService",
    "TwitterService",
    "FacebookService",
    "InstagramService",
    "LinkedInService",
    "YouTubeService",
    "TikTokService"
]

# Platform version information
__version__ = "2.0.0"
__author__ = "Skeduluk devs"

# Platform service registry (for dynamic lookups)
PLATFORM_REGISTRY = {
    "TWITTER": TwitterService,
    "FACEBOOK": FacebookService,
    "INSTAGRAM": InstagramService,
    "LINKEDIN": LinkedInService,
    "YOUTUBE": YouTubeService,
    "TIKTOK":TikTokService
}

def get_platform_service(platform_name: str):
    return PLATFORM_REGISTRY.get(platform_name.upper())