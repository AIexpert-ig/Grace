"""Grace AI Infrastructure - Core API."""
import hmac
import hashlib
import time
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
# --- CORRECTED IMPORT ---
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
telegram_service = TelegramService()

# 2. Lifespan Manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # THE SYNC TAG (Verify this in Railway logs)
    logger.info("🚀 GRACE AI Infrastructure Online [V2.0-SYNCED-DUBAI]")
    try:
        from app.core.database import Base, get_engine
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables verified/created")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
    yield

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(staff.router, prefix="/staff")

@app.get("/")
async def root(): return {"message": "Grace Gateway Online"}

@app.post("/staff/escalate")
async def escalate(request: Request, authenticated: bool = Depends(verify_hmac_signature)):
    # This route will now trigger the HMAC_DEBUG logs in app/auth.py
    return {"status": "success", "message": "Escalation received"}