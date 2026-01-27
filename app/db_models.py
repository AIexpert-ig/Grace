from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String, index=True)
    guest_name = Column(String)
    issue = Column(String)
    
    # Timeline for performance tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Staff Identity
    claimed_by = Column(String, nullable=True)
    status = Column(String, default="PENDING") # PENDING -> IN_PROGRESS -> RESOLVED

    def to_dict(self, room_type: RoomType) -> dict:
        """Convert rate to dictionary for API response."""
        rate_value = self.standard_rate if room_type == RoomType.STANDARD else self.suite_rate
        return {
            "rate": str(rate_value),
            "currency": "AED",
            "availability": self.availability
        }
