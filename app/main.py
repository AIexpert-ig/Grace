"""FastAPI application for Grace AI Infrastructure."""
from fastapi import FastAPI, BackgroundTasks
from .models import RateCheckRequest, CallSummaryRequest
from .services.telegram import TelegramService
from .core.config import settings

# MOCK DB (Goal: Replace with real logic later)
RATE_DB = {
    "2026-01-22": {"standard": 500, "suite": 950, "availability": "High"},
    "2026-01-23": {"standard": 550, "suite": 1000, "availability": "Low"},
}

app = FastAPI(title=settings.PROJECT_NAME)
telegram_service = TelegramService()


@app.post("/check-rates")
async def check_rates(data: RateCheckRequest):
    """Check hotel rates for a given check-in date and room type."""
    # CRITICAL: Returns raw numbers. No Math.
    rate_info = RATE_DB.get(data.check_in_date)
    if not rate_info:
        return {"rate": "N/A", "availability": "None"}

    price = rate_info.get(data.room_type.lower(), rate_info["standard"])
    return {"rate": str(price), "currency": "AED", "availability": rate_info["availability"]}


@app.post("/post-call-webhook")
async def post_call_webhook(data: CallSummaryRequest, background_tasks: BackgroundTasks):
    """Process call summary webhook and send alerts for high/medium urgency calls."""
    if data.urgency.lower() in ["high", "medium"]:
        background_tasks.add_task(
            telegram_service.send_alert,
            f"High urgency call from {data.caller_name}. Summary: {data.summary}"
        )
    return {"status": "processed"}
