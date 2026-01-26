"""FastAPI application for Grace AI Infrastructure."""
import logging
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from .models import RateCheckRequest, CallSummaryRequest, UrgencyLevel
from .services.telegram import TelegramService
from .services.rate_service import RateService
from .core.config import settings
from .core.database import get_db, get_pool_status
from .core.hmac_auth import verify_hmac_signature
from .core.validators import validate_check_in_date_not_past

# Configure standard Python logging for production
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)

# --- SECURITY MIDDLEWARE ---
# In production, replace ["*"] with your actual frontend domains and load balancer IPs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"]
)

telegram_service = TelegramService()

@app.on_event("startup")
async def startup_event():
    """Initialize database connection pool on startup."""
    pool_status = get_pool_status()
    logger.info(f"Database connection pool initialized: {pool_status}")

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on shutdown."""
    from .core import database
    if database.engine is None:
        logger.info("Database connections were not initialized.")
        return
    await database.engine.dispose()
    logger.info("Database connections closed.")

@app.get("/health")
async def health_check():
    """Health check endpoint with connection pool status."""
    return {
        "status": "healthy",
        "pool": get_pool_status()
    }

@app.post("/check-rates")
async def check_rates(
    data: RateCheckRequest,
    db: AsyncSession = Depends(get_db)
):
    """Check hotel rates for a given check-in date and room type."""
    # 1. Deterministic Timezone Validation
    try:
        validate_check_in_date_not_past(data.check_in_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # 2. Fetch from Service Layer (No SQL here!)
    rate = await RateService.get_rate_for_date(db, data.check_in_date)

    if not rate:
        logger.warning(f"Rate check failed: No rates for {data.check_in_date}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rates available for check-in date: {data.check_in_date.isoformat()}"
        )

    # 3. Validate Room Type Availability
    if not getattr(rate, f"{data.room_type.value}_rate"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room type '{data.room_type.value}' not available for this date"
        )

    # 4. Format and Return
    return RateService.format_rate_response(rate, data.room_type)

# Notice: route_class=HMACVerifiedRoute has been removed!
@app.post("/post-call-webhook")
async def post_call_webhook(
    background_tasks: BackgroundTasks,
    body_data: dict = Depends(verify_hmac_signature)
):
    """Process call summary webhook with HMAC signature validation."""
    # Parse the verified body data into the model
    data = CallSummaryRequest(**body_data)
    
    if data.urgency in [UrgencyLevel.HIGH, UrgencyLevel.MEDIUM]:
        urgency_label = data.urgency.value.capitalize()
        message = (
            f"{urgency_label} urgency call from {data.caller_name} (Room {data.room_number}). "
            f"Summary: {data.summary}. Callback: {data.callback_number}"
        )
        logger.info(f"Triggering Telegram alert for high urgency call from {data.caller_name}")
        background_tasks.add_task(telegram_service.send_alert, message)
        
    return {"status": "processed"}


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    """Process Telegram webhook updates separately from voice AI."""
    data = await request.json()
    await telegram_service.process_update(data)
    return {"ok": True}


STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
