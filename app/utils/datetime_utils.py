# app/utils/datetime_utils.py
"""
Utilities for handling datetime conversions.
Ensures consistent timezone handling across the application.
"""

from datetime import datetime, timezone
from typing import Optional


def make_timezone_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convert timezone-aware datetime to timezone-naive.
    Required for PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns.
    
    Args:
        dt: Datetime object (can be timezone-aware or naive)
        
    Returns:
        Timezone-naive datetime in UTC, or None if input is None
        
    Example:
        >>> dt = datetime(2026, 1, 5, 15, 34, tzinfo=timezone.utc)
        >>> make_timezone_naive(dt)
        datetime.datetime(2026, 1, 5, 15, 34)
    """
    if dt is None:
        return None
    
    if dt.tzinfo is not None:
        # Convert to UTC and remove timezone
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.replace(tzinfo=None)
    
    # Already naive, return as-is
    return dt


def make_timezone_aware(dt: Optional[datetime], tz=timezone.utc) -> Optional[datetime]:
    """
    Convert timezone-naive datetime to timezone-aware.
    Assumes naive datetimes are in UTC.
    
    Args:
        dt: Datetime object (can be timezone-aware or naive)
        tz: Timezone to use (default: UTC)
        
    Returns:
        Timezone-aware datetime, or None if input is None
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=tz)
    
    # Already aware
    return dt


def utcnow_naive() -> datetime:
    """
    Get current UTC time as timezone-naive datetime.
    Use this for database operations with TIMESTAMP WITHOUT TIME ZONE.
    
    Returns:
        Current UTC time without timezone info
    """
    return datetime.utcnow()


def utcnow_aware() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.
    Use this for API responses and calculations.
    
    Returns:
        Current UTC time with timezone info
    """
    return datetime.now(timezone.utc)