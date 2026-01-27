from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean
from sqlalchemy.sql import func
from app.core.database import Base

class Rate(Base):
    __tablename__ = "rates"
    
    id = Column(Integer, primary_key=True, index=True)
    room_type = Column(String, index=True)
    currency = Column(String, default="USD", index=True)
    rate = Column(Float)
    
    # Fields required to pass test_check_rates_no_availability
    check_in_date = Column(DateTime, index=True)
    check_out_date = Column(DateTime, index=True)
    is_available = Column(Boolean, default=True)
    
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Escalation(Base):
    __tablename__ = "escalations"
    
    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String, index=True)
    guest_name = Column(String)
    issue = Column(String)
    
    # Timeline and Status
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    claimed_by = Column(String, nullable=True)
    status = Column(String, default="PENDING") # PENDING -> IN_PROGRESS -> RESOLVED