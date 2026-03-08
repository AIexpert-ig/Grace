"""Pydantic models for request validation."""
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


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


class CallSummaryRequest(BaseModel):  # pylint: disable=too-few-public-methods
    """Request model for call summary webhook."""

    caller_name: str = Field(..., min_length=1, description="Name of the caller")
    room_number: str = Field(..., min_length=1, description="Room number")
    callback_number: str = Field(..., min_length=1, description="Phone number for callback")
    summary: str = Field(..., min_length=1, description="Summary of the call")
    urgency: UrgencyLevel = Field(..., description="Urgency level of the call")

# --- SQLAlchemy Models ---
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db import Base as DbBase

class Escalation(DbBase):
    __tablename__ = "escalations"
    id = Column(Integer, primary_key=True, index=True)
    guest_name = Column(String, default="Unknown Guest")
    room_number = Column(String, default="Unknown")
    issue = Column(Text)
    status = Column(String, default="OPEN")
    sentiment = Column(String, default="Neutral")
    created_at = Column(DateTime, default=datetime.utcnow)

class Event(DbBase):
    __tablename__ = "dashboard_events"
    id = Column(Integer, primary_key=True, index=True)
    at = Column(DateTime, default=datetime.utcnow, index=True)
    type = Column(String, default="info")
    source = Column(String, default="system")
    text = Column(Text)
    payload = Column(Text, nullable=True)

class CallSession(DbBase):
    __tablename__ = "call_sessions"
    id = Column(String, primary_key=True, index=True)
    from_contact = Column(String, default="")
    status = Column(String, default="Active")
    intent = Column(String, default="")
    latency_ms = Column(Integer, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    transcript_snippet = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StaffMember(DbBase):
    __tablename__ = "staff_members"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, default="")
    role = Column(String, default="")
    shift = Column(String, default="")
    phone = Column(String, default="")
    status = Column(String, default="")
    languages = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
