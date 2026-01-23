"""FastAPI application for Grace AI Infrastructure."""
import logging

from sqlalchemy.ext.asyncio import AsyncSession  # pyright: ignore[reportMissingImports]
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .models import RateCheckRequest, CallSummaryRequest, UrgencyLevel
from .services.rate_service import RateService
from .services.telegram import TelegramService
from .core.config import settings
from .core.database import get_db, get_pool_status
from .core.hmac_auth import verify_hmac_signature
from .core.validators import validate_check_in_date_not_past

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)
telegram_service = TelegramService()
rate_service = RateService()

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure with actual allowed hosts in production
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure with actual origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    # Validate date is not in the past (property timezone-aware)
    try:
        validate_check_in_date_not_past(data.check_in_date)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Get rate from service layer
    try:
        return await rate_service.get_rate_by_date(db, data.check_in_date, data.room_type)
    except ValueError as e:
        if "No rates available" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.post("/post-call-webhook")
async def post_call_webhook(
    background_tasks: BackgroundTasks,
    body_data: dict = Depends(verify_hmac_signature)
):
    """Process call summary webhook with HMAC signature validation.
    
    The request body is read and verified by the HMAC dependency, which
    returns the parsed JSON body. HMAC signature prevents tampering
    and replay attacks.
    """
    # Parse the verified body data into the model
    # body_data is already parsed JSON from verify_hmac_signature
    data = CallSummaryRequest(**body_data)
    
    if data.urgency in [UrgencyLevel.HIGH, UrgencyLevel.MEDIUM]:
        urgency_label = data.urgency.value.capitalize()
        background_tasks.add_task(
            telegram_service.send_alert,
            f"{urgency_label} urgency call from {data.caller_name} (Room {data.room_number}). "
            f"Summary: {data.summary}. Callback: {data.callback_number}"
        )
    return {"status": "processed"}
