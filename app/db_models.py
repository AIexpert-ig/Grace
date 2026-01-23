"""SQLAlchemy database models."""
from sqlalchemy import Column, Date, Integer, String  # pyright: ignore[reportMissingImports]

from .core.database import Base
from .models import RoomType


class Rate(Base):  # pylint: disable=too-few-public-methods
    """Database model for hotel rates."""

    __tablename__ = "rates"

    id = Column(Integer, primary_key=True, index=True)
    check_in_date = Column(Date, nullable=False, index=True, unique=True)
    standard_rate = Column(Integer, nullable=False)
    suite_rate = Column(Integer, nullable=False)
    availability = Column(String(50), nullable=False, default="High")

    def to_dict(self, room_type: RoomType) -> dict:
        """Convert rate to dictionary for API response."""
        rate_value = self.standard_rate if room_type == RoomType.STANDARD else self.suite_rate
        return {
            "rate": str(rate_value),
            "currency": "AED",
            "availability": self.availability
        }
