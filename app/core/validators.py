"""Business logic validators."""
import logging
from datetime import date, datetime

import pytz

from .config import settings

logger = logging.getLogger(__name__)


def validate_check_in_date_not_past(check_in_date: date) -> date:
    """Validate that check-in date is not in the past (property timezone-aware).
    
    This business logic is separated from the Pydantic model to ensure
    deterministic behavior and allow reuse in different contexts (API, workers, etc.).
    
    Uses the property's local timezone (e.g., Asia/Dubai) to validate dates.
    This ensures that a guest booking "today" at the front desk is valid,
    regardless of where the server is located or what UTC time it is.
    
    Example: At 2:00 AM Dubai time (Jan 24), UTC is 10:00 PM (Jan 23).
    A booking for Jan 24 should be valid because it's "today" in Dubai.
    
    Args:
        check_in_date: The date to validate
        
    Returns:
        date: The validated date (unchanged if valid)
        
    Raises:
        ValueError: If date is in the past or timezone is invalid
    """
    try:
        property_tz = pytz.timezone(settings.PROPERTY_TIMEZONE)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(
            "Invalid timezone configuration",
            extra={"timezone": settings.PROPERTY_TIMEZONE}
        )
        raise ValueError(
            f"Invalid timezone '{settings.PROPERTY_TIMEZONE}'. "
            "Use IANA timezone name (e.g., Asia/Dubai, America/New_York)"
        )

    # Get current date in property's local timezone
    now_property = datetime.now(property_tz)
    today_property = now_property.date()

    if check_in_date < today_property:
        logger.warning(
            "Check-in date validation failed - date in past",
            extra={
                "check_in_date": check_in_date.isoformat(),
                "today_property": today_property.isoformat(),
                "timezone": settings.PROPERTY_TIMEZONE
            }
        )
        raise ValueError(
            f"Check-in date cannot be in the past. "
            f"Today ({settings.PROPERTY_TIMEZONE}): {today_property}, Provided: {check_in_date}"
        )
    return check_in_date
