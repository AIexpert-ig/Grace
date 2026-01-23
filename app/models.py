"""Pydantic models for request validation."""
from datetime import date, datetime
from enum import Enum

import pytz  # pyright: ignore[reportMissingModuleSource]
from pydantic import BaseModel, Field, field_validator

from .core.config import settings


class RoomType(str, Enum):
    """Enumeration of available room types."""

    STANDARD = "standard"
    SUITE = "suite"


class UrgencyLevel(str, Enum):
    """Enumeration of urgency levels for call summaries."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RateCheckRequest(BaseModel):  # pylint: disable=too-few-public-methods
    """Request model for checking hotel rates."""

    check_in_date: date = Field(..., description="Check-in date in YYYY-MM-DD format")
    room_type: RoomType = Field(default=RoomType.STANDARD, description="Type of room")

    @field_validator("check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: date) -> date:
        """Validate that check-in date is not in the past (property timezone-aware).
        
        Uses the property's local timezone (e.g., Asia/Dubai) to validate dates.
        This ensures that a guest booking "today" at the front desk is valid,
        regardless of where the server is located or what UTC time it is.
        
        Example: At 2:00 AM Dubai time (Jan 24), UTC is 10:00 PM (Jan 23).
        A booking for Jan 24 should be valid because it's "today" in Dubai.
        """
        try:
            property_tz = pytz.timezone(settings.PROPERTY_TIMEZONE)
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(
                f"Invalid timezone '{settings.PROPERTY_TIMEZONE}'. "
                "Use IANA timezone name (e.g., Asia/Dubai, America/New_York)"
            )
        
        # Get current date in property's local timezone
        now_property = datetime.now(property_tz)
        today_property = now_property.date()
        
        if v < today_property:
            raise ValueError(
                f"Check-in date cannot be in the past. "
                f"Today ({settings.PROPERTY_TIMEZONE}): {today_property}, Provided: {v}"
            )
        return v


class CallSummaryRequest(BaseModel):  # pylint: disable=too-few-public-methods
    """Request model for call summary webhook."""

    caller_name: str = Field(..., min_length=1, description="Name of the caller")
    room_number: str = Field(..., min_length=1, description="Room number")
    callback_number: str = Field(..., min_length=1, description="Phone number for callback")
    summary: str = Field(..., min_length=1, description="Summary of the call")
    urgency: UrgencyLevel = Field(..., description="Urgency level of the call")
