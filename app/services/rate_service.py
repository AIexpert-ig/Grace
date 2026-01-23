"""Rate service for database operations."""
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db_models import Rate
from ..models import RoomType

logger = logging.getLogger(__name__)


class RateService:  # pylint: disable=too-few-public-methods
    """Service for rate-related database operations."""

    @staticmethod
    async def get_rate_by_date(
        db: AsyncSession,
        check_in_date: date,
        room_type: RoomType
    ) -> dict:
        """Get rate information for a specific check-in date and room type.
        
        Args:
            db: Database session
            check_in_date: Check-in date
            room_type: Type of room (standard or suite)
            
        Returns:
            dict: Rate information with rate, currency, and availability
            
        Raises:
            ValueError: If rate not found or room type not available
        """
        stmt = select(Rate).where(Rate.check_in_date == check_in_date)
        result = await db.execute(stmt)
        rate = result.scalar_one_or_none()

        if not rate:
            logger.warning(
                "Rate not found for date",
                extra={"check_in_date": check_in_date.isoformat()}
            )
            raise ValueError(f"No rates available for check-in date: {check_in_date.isoformat()}")

        # Validate room type exists
        if room_type == RoomType.STANDARD and not rate.standard_rate:
            raise ValueError(f"Room type '{room_type.value}' not available for this date")
        if room_type == RoomType.SUITE and not rate.suite_rate:
            raise ValueError(f"Room type '{room_type.value}' not available for this date")

        logger.info(
            "Rate retrieved successfully",
            extra={
                "check_in_date": check_in_date.isoformat(),
                "room_type": room_type.value
            }
        )
        return rate.to_dict(room_type)
