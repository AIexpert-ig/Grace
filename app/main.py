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
from .core.hmac_auth import verify_hmac_signature
from .core.validators import validate_check_in_date_not_past
from .routers import staff

# 1. Standardized Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 2. Global Services
telegram_service = TelegramService()

# 3. Modern Lifespan Manager (Replaces @app.on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify system integrity on boot and handle shutdown."""
    logger.info("🚀 GRACE AI Infrastructure Starting Up")
    
    # DB Check
    logger.info(f"💾 DB Pool Status: {get_pool_status()}")
    
    # AI Audit
    key = settings.OPENAI_API_KEY
    if not key:
        logger.error("❌ CRITICAL: OPENAI_API_KEY is missing!")
    else:
        logger.info(f"✅ AI CORE ACTIVE: Key verified ({key[:12]}...)")
        
    yield
    
    logger.info("💤 GRACE AI Infrastructure Shutting Down")

# 4. Single App Initialization
app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# 5. Middleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 6. Register Routers
app.include_router(staff.router, prefix="/staff")

# --- ENDPOINTS ---

@app.get("/")
async def root():
    return {"message": "Grace Gateway Online"}

@app.get("/health")
async def health():
    return {"status": "online", "key_loaded": bool(settings.OPENAI_API_KEY)}

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    await telegram_service.process_update(data)
    return {"ok": True}

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

# 7. Static Files (Handled last)
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")