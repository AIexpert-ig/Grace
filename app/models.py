"""Pydantic models for request validation."""
from pydantic import BaseModel


class RateCheckRequest(BaseModel):
    """Request model for checking hotel rates."""

    check_in_date: str
    room_type: str = "standard"


class CallSummaryRequest(BaseModel):
    """Request model for call summary webhook."""

    caller_name: str
    room_number: str
    callback_number: str
    summary: str
    urgency: str
