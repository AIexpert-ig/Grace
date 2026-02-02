"""Grace AI Infrastructure - Core API."""
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from .models import RateCheckRequest, CallSummaryRequest, UrgencyLevel
from .services.telegram import TelegramService
from .services.rate_service import RateService
from .core.config import settings
from .core.database import get_db, get_pool_status
from .auth import verify_hmac_signature
from .core.validators import validate_check_in_date_not_past
from .routers import staff
from .routers.staff import telegram_callback

# 1. Standardized Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 2. Global Services
telegram_service = TelegramService()

# 3. Version & Build Info
VERSION = "2.1.0"
BUILD_DATE = "2026-02-02"

def mask_secret(secret: str, show_chars: int = 4) -> str:
    """Safely mask secrets for logging - shows first N chars only."""
    if not secret or len(secret) <= show_chars:
        return "***NOT SET***" if not secret else "****"
    return f"{secret[:show_chars]}{'*' * (len(secret) - show_chars)}"

# 4. Modern Lifespan Manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify system integrity on boot with enhanced diagnostics."""
    logger.info("=" * 60)
    logger.info(f"🚀 GRACE AI Infrastructure v{VERSION} [{BUILD_DATE}]")
    logger.info("=" * 60)
    
    # Configuration Status (masked for security)
    logger.info("� Configuration Status:")
    logger.info(f"   ├── API Key: {mask_secret(settings.API_KEY)}")
    logger.info(f"   ├── HMAC Secret: {mask_secret(settings.HMAC_SECRET)}")
    logger.info(f"   ├── OpenAI Key: {'✅ Configured' if settings.OPENAI_API_KEY else '❌ Missing'}")
    logger.info(f"   ├── Telegram Bot: {'✅ Configured' if settings.TELEGRAM_BOT_TOKEN else '❌ Missing'}")
    logger.info(f"   └── Database: {'✅ Connected' if settings.DATABASE_URL else '❌ Missing'}")
    
    # Auto-create database tables if they don't exist
    try:
        from app.core.database import Base, get_engine
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables verified/created")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
    
    logger.info(f"💾 DB Pool Status: {get_pool_status()}")
    logger.info("🟢 System Ready - Accepting Requests")
    logger.info("=" * 60)
    
    yield
    
    logger.info("=" * 60)
    logger.info("💤 GRACE AI Infrastructure Shutting Down...")
    logger.info("=" * 60)

# 5. App Initialization
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=VERSION,
    description="Grace AI - Intelligent Hospitality Infrastructure",
    lifespan=lifespan
)

# 6. Middleware & Routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(staff.router, prefix="/staff", tags=["Staff Operations"])

# --- ENDPOINTS ---

@app.get("/", tags=["System"])
async def root():
    """Root endpoint - system status."""
    return {
        "service": "Grace AI Gateway",
        "version": VERSION,
        "status": "online"
    }

@app.get("/health", tags=["System"])
async def health():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": VERSION,
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN),
        "database_pool": get_pool_status()
    }

@app.post("/telegram-webhook", tags=["Telegram"])
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Entry point for all Telegram signals (Buttons & Text)."""
    data = await request.json()
    
    # HANDLER 1: Interactive Button Clicks (callback_query)
    if "callback_query" in data:
        logger.info("🔘 Button click detected. Routing to staff callback.")
        return await telegram_callback(data, db)
    
    # HANDLER 2: Standard AI/Text Processing
    await telegram_service.process_update(data)
    return {"ok": True}

@app.post("/check-rates", tags=["Rates"])
async def check_rates(data: RateCheckRequest, db: AsyncSession = Depends(get_db)):
    """Check room rates for a specific date."""
    try:
        validate_check_in_date_not_past(data.check_in_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    
    rate = await RateService.get_rate_for_date(db, data.check_in_date)
    if not rate:
        raise HTTPException(status_code=404, detail="No rates found for this date.")
    return RateService.format_rate_response(rate, data.room_type)

@app.post("/post-call-webhook", tags=["Webhooks"])
async def post_call_webhook(
    background_tasks: BackgroundTasks,
    body_data: dict = Depends(verify_hmac_signature)
):
    """Secure webhook for post-call processing with HMAC verification."""
    data = CallSummaryRequest(**body_data)
    
    if data.urgency in [UrgencyLevel.HIGH, UrgencyLevel.MEDIUM]:
        msg = f"🛎 *{data.urgency.value.upper()} URGENCY*\nGuest: {data.caller_name}\nSummary: {data.summary}"
        background_tasks.add_task(telegram_service.send_alert, msg)
        logger.info(f"📨 Alert queued for {data.urgency.value} urgency call from {data.caller_name}")
    
    return {"status": "processed", "urgency": data.urgency.value}

# 7. Static Files
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")