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

# 3. Modern Lifespan Manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify system integrity on boot."""
    logger.info("🚀 GRACE AI Infrastructure Online [V2.0-SYNCED-DUBAI]")  
    logger.info("🔑 API Key: " + settings.API_KEY)
    logger.info("🔑 HMAC Secret: " + settings.HMAC_SECRET)
   logger.info("🔑 OpenAI API Key: " + settings.OPENAI_API_KEY)
    logger.info("🔑 Telegram Bot Token: " + settings.TELEGRAM_BOT_TOKEN)    
    # Auto-create database tables if they don't exist
    logger.info("🔑 Database Tables: " + settings.DATABASE_URL)
    try:    
        from app.core.database import Base, get_engine
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables verified/created")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
    
    logger.info(f"💾 DB Pool Status: {get_pool_status()}")
    yield
    logger.info("💤 GRACE AI Infrastructure Offline")

# 4. App Initialization
app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# 5. Middleware & Routers
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(staff.router, prefix="/staff")

# --- ENDPOINTS ---

@app.post("/telegram-webhook")
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

@app.get("/")
async def root():
    return {"message": "Grace Gateway Online"}

@app.get("/health")
async def health():
    return {"status": "online", "key_loaded": bool(settings.OPENAI_API_KEY)}

@app.post("/check-rates")
async def check_rates(data: RateCheckRequest, db: AsyncSession = Depends(get_db)):
    try:
        validate_check_in_date_not_past(data.check_in_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    
    rate = await RateService.get_rate_for_date(db, data.check_in_date)
    if not rate:
        raise HTTPException(status_code=404, detail="No rates found for this date.")
    return RateService.format_rate_response(rate, data.room_type)

@app.post("/post-call-webhook")
async def post_call_webhook(background_tasks: BackgroundTasks, body_data: dict = Depends(verify_hmac_signature)):
    data = CallSummaryRequest(**body_data)
    if data.urgency in [UrgencyLevel.HIGH, UrgencyLevel.MEDIUM]:
        msg = f"🛎 *{data.urgency.value.upper()} URGENCY*\nGuest: {data.caller_name}\nSummary: {data.summary}"
        background_tasks.add_task(telegram_service.send_alert, msg)
    return {"status": "processed"}

# 6. Static Files
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")