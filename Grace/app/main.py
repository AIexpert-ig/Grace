import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from .auth import verify_hmac_signature

logger = logging.getLogger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # If you see this in Railway logs, the Brain is finally synced.
    logger.info("🚀 GRACE AI Infrastructure Online [V2.0-SYNCED-DUBAI]")
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/staff/escalate")
async def escalate(request: Request, authenticated: bool = Depends(verify_hmac_signature)):
    return {"status": "success", "message": "Escalation received"}# Force Sync: Mon Feb  2 10:46:05 +04 2026
# Force Build Hash: 13297
# Sync-Hash: 13924
# Build-Force: Mon Feb  2 10:57:14 +04 2026
