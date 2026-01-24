"""Service layer for rate-related database operations."""
from datetime import date
from sqlalchemy import select  # pyright: ignore[reportMissingImports]
from sqlalchemy.ext.asyncio import AsyncSession  # pyright: ignore[reportMissingImports]

from app.db_models import Rate
from app.models import RoomType

class RateService:
    """Service for handling hotel rate queries."""

    @staticmethod
    async def get_rate_for_date(db: AsyncSession, check_in_date: date) -> Rate | None:
        """Fetch rate information for a specific date from the database.
        
        Args:
            db: The async database session
            check_in_date: The date to check rates for
            
        Returns:
            Rate object if found, None otherwise
        """
        stmt = select(Rate).where(Rate.check_in_date == check_in_date)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def format_rate_response(rate: Rate, room_type: RoomType) -> dict:
        """Format the database rate object into the API response dictionary."""
        return rate.to_dict(room_type)