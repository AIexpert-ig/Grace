"""FastAPI application for Grace AI Infrastructure."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, status
from .models import RateCheckRequest, CallSummaryRequest, RoomType, UrgencyLevel
from .services.telegram import TelegramService
from .core.config import settings
from .core.database import get_db, get_pool_status
from .core.hmac_auth import verify_hmac_signature
from .db_models import Rate

app = FastAPI(title=settings.PROJECT_NAME)
telegram_service = TelegramService()


@app.on_event("startup")
async def startup_event():
    """Initialize database connection pool on startup."""
    # Verify connection pool is ready
    pool_status = get_pool_status()
    app.state.pool_status = pool_status


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on shutdown."""
    from .core.database import engine
    await engine.dispose()


@app.get("/health")
async def health_check():
    """Health check endpoint with connection pool status."""
    pool_status = get_pool_status()
    return {
        "status": "healthy",
        "pool": pool_status
    }


@app.post("/check-rates")
async def check_rates(
    data: RateCheckRequest,
    db: AsyncSession = Depends(get_db)
):
    """Check hotel rates for a given check-in date and room type."""
    # CRITICAL: Returns raw numbers. No Math.
    # Query database for rate
    stmt = select(Rate).where(Rate.check_in_date == data.check_in_date)
    result = await db.execute(stmt)
    rate = result.scalar_one_or_none()

    if not rate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rates available for check-in date: {data.check_in_date.isoformat()}"
        )

    # Validate room type exists
    if data.room_type == RoomType.STANDARD and not rate.standard_rate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room type '{data.room_type.value}' not available for this date"
        )
    if data.room_type == RoomType.SUITE and not rate.suite_rate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room type '{data.room_type.value}' not available for this date"
        )

    return rate.to_dict(data.room_type)


@app.post("/post-call-webhook")
async def post_call_webhook(
    background_tasks: BackgroundTasks,
    body_data: dict = Depends(verify_hmac_signature)
):
    """Process call summary webhook with HMAC signature validation.
    
    The request body is read and verified by the HMAC dependency.
    HMAC signature prevents tampering and replay attacks.
    """
    # Parse the verified body data into the model
    data = CallSummaryRequest(**body_data)
    
    if data.urgency in [UrgencyLevel.HIGH, UrgencyLevel.MEDIUM]:
        urgency_label = data.urgency.value.capitalize()
        background_tasks.add_task(
            telegram_service.send_alert,
            f"{urgency_label} urgency call from {data.caller_name} (Room {data.room_number}). "
            f"Summary: {data.summary}. Callback: {data.callback_number}"
        )
    return {"status": "processed"}
