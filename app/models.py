"""Pydantic models for request validation."""
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from .core.validators import validate_check_in_date_not_past


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
    def check_date_not_past(cls, value: date) -> date:
        """Ensure check-in date is not in the past."""
        validate_check_in_date_not_past(value)
        return value


class CallSummaryRequest(BaseModel):  # pylint: disable=too-few-public-methods
    """Request model for call summary webhook."""

    caller_name: str = Field(..., min_length=1, description="Name of the caller")
    room_number: str = Field(..., min_length=1, description="Room number")
    callback_number: str = Field(..., min_length=1, description="Phone number for callback")
    summary: str = Field(..., min_length=1, description="Summary of the call")
    urgency: UrgencyLevel = Field(..., description="Urgency level of the call")
