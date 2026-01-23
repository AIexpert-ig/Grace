"""Pydantic models for request validation."""
from pydantic import BaseModel


class RateCheckRequest(BaseModel):  # pylint: disable=too-few-public-methods
    """Request model for checking hotel rates."""

    check_in_date: str
    room_type: str = "standard"


class CallSummaryRequest(BaseModel):  # pylint: disable=too-few-public-methods
    """Request model for call summary webhook."""

    caller_name: str
    room_number: str
    callback_number: str
    summary: str
    urgency: str
