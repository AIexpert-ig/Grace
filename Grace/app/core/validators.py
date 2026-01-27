"""Deterministic validation logic for business rules."""
from datetime import date, datetime
import pytz
from .config import settings

def validate_check_in_date_not_past(check_in_date: date) -> None:
    """Validate that check-in date is not in the past using the property's local timezone.
    
    Raises:
        ValueError: If the date is in the past or timezone is invalid.
    """
    try:
        property_tz = pytz.timezone(settings.PROPERTY_TIMEZONE)
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(
            f"Invalid timezone '{settings.PROPERTY_TIMEZONE}'. "
            "Use IANA timezone name (e.g., Asia/Dubai)"
        )
    
    # Get current date in property's local timezone
    now_property = datetime.now(property_tz)
    today_property = now_property.date()
    
    if check_in_date < today_property:
        raise ValueError(
            f"Check-in date cannot be in the past. "
            f"Today ({settings.PROPERTY_TIMEZONE}): {today_property}, Provided: {check_in_date}"
        )