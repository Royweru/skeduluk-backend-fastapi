# app/utils/scheduling_utils.py
"""
Scheduling utilities for post scheduling validation and management.

This module provides:
- Minimum scheduling time validation
- Time rounding to nearest slot
- Scheduling rules based on content type
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple


class SchedulingError(Exception):
    """Exception raised when scheduling validation fails."""

    def __init__(self, message: str, min_time: datetime = None):
        self.message = message
        self.min_time = min_time
        super().__init__(self.message)


# Minimum lead times in minutes
MINIMUM_LEAD_TIME_TEXT = 15      # Text/image posts
MINIMUM_LEAD_TIME_VIDEO = 30    # Short video (< 5 min)
MINIMUM_LEAD_TIME_LONG_VIDEO = 45  # Long video (> 5 min)

# Time slot rounding (in minutes)
SLOT_INTERVAL = 5  # Round to nearest 5 minutes


def get_minimum_lead_time(
    has_video: bool = False,
    video_duration_seconds: Optional[int] = None
) -> int:
    """
    Get the minimum lead time in minutes based on content type.

    Args:
        has_video: Whether the post contains video content
        video_duration_seconds: Duration of video in seconds (if applicable)

    Returns:
        Minimum lead time in minutes
    """
    if not has_video:
        return MINIMUM_LEAD_TIME_TEXT

    if video_duration_seconds and video_duration_seconds > 300:  # > 5 minutes
        return MINIMUM_LEAD_TIME_LONG_VIDEO

    return MINIMUM_LEAD_TIME_VIDEO


def round_to_nearest_slot(dt: datetime) -> datetime:
    """
    Round datetime to the nearest scheduling slot.

    Rounds up to the next 5-minute interval.
    Example: 09:07 -> 09:10, 09:11 -> 09:15

    Args:
        dt: Datetime to round

    Returns:
        Rounded datetime
    """
    # Calculate minutes to add to reach next slot
    minutes = dt.minute
    remainder = minutes % SLOT_INTERVAL

    if remainder == 0:
        # Already on a slot boundary
        return dt.replace(second=0, microsecond=0)

    # Round up to next slot
    minutes_to_add = SLOT_INTERVAL - remainder
    return dt.replace(second=0, microsecond=0) + timedelta(minutes=minutes_to_add)


def validate_scheduled_time(
    scheduled_for: datetime,
    has_video: bool = False,
    video_duration_seconds: Optional[int] = None,
    reference_time: Optional[datetime] = None
) -> Tuple[bool, str]:
    """
    Validate that a scheduled time meets minimum lead time requirements.

    Args:
        scheduled_for: The proposed scheduling datetime (should be UTC)
        has_video: Whether the post contains video content
        video_duration_seconds: Duration of video in seconds (if applicable)
        reference_time: Reference time to compare against (defaults to now UTC)

    Returns:
        Tuple of (is_valid, message)

    Raises:
        SchedulingError: If the scheduled time is invalid
    """
    now = reference_time or datetime.utcnow()

    # Get minimum lead time based on content type
    min_lead_time = get_minimum_lead_time(has_video, video_duration_seconds)
    min_allowed_time = now + timedelta(minutes=min_lead_time)

    # Check if scheduled time is in the past
    if scheduled_for < now:
        raise SchedulingError(
            "Cannot schedule posts in the past.",
            min_time=round_to_nearest_slot(min_allowed_time)
        )

    # Check if scheduled time meets minimum lead time
    time_until_post = scheduled_for - now
    if time_until_post < timedelta(minutes=min_lead_time):
        content_type = "video" if has_video else "text/image"
        readable_min_time = round_to_nearest_slot(min_allowed_time)

        raise SchedulingError(
            f"Posts with {content_type} content must be scheduled at least "
            f"{min_lead_time} minutes in advance. "
            f"Earliest available time: {readable_min_time.strftime('%Y-%m-%d %H:%M')} UTC",
            min_time=readable_min_time
        )

    return True, "Scheduling time is valid"


def get_earliest_schedule_time(
    has_video: bool = False,
    video_duration_seconds: Optional[int] = None,
    reference_time: Optional[datetime] = None
) -> datetime:
    """
    Get the earliest valid scheduling time for given content type.

    Args:
        has_video: Whether the post contains video content
        video_duration_seconds: Duration of video in seconds (if applicable)
        reference_time: Reference time to calculate from (defaults to now UTC)

    Returns:
        Earliest valid scheduling datetime (rounded to nearest slot)
    """
    now = reference_time or datetime.utcnow()
    min_lead_time = get_minimum_lead_time(has_video, video_duration_seconds)
    earliest = now + timedelta(minutes=min_lead_time)

    return round_to_nearest_slot(earliest)


def format_time_until(target_time: datetime, reference_time: Optional[datetime] = None) -> str:
    """
    Format the time remaining until a target time.

    Args:
        target_time: Target datetime
        reference_time: Reference time (defaults to now UTC)

    Returns:
        Human-readable string like "2 hours 15 minutes"
    """
    now = reference_time or datetime.utcnow()
    delta = target_time - now

    if delta.total_seconds() < 0:
        return "in the past"

    total_minutes = int(delta.total_seconds() / 60)

    if total_minutes < 60:
        return f"{total_minutes} minute{'s' if total_minutes != 1 else ''}"

    hours = total_minutes // 60
    minutes = total_minutes % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

    return " ".join(parts)
