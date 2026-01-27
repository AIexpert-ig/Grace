import os
import httpx
from fastapi import APIRouter, Depends
from app.auth import verify_hmac_signature
from app.templates.notifications import StaffAlertTemplate

router = APIRouter()

# Load credentials from Railway Variables
# app/routers/staff.py

# This tells Python: "Go to Railway and find the value stored under these names"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
STAFF_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

@router.post("/escalate", dependencies=[Depends(verify_hmac_signature)])
async def trigger_escalation(data: dict):
    # 1. Generate the world-class UI message
    formatted_msg = StaffAlertTemplate.format_urgent_escalation(
        data.get('guest_name', 'Unknown Guest'),
        data.get('room_number', 'N/A'),
        data.get('issue', 'General Assistance')
    )

    # 2. Transmit to Telegram Staff Channel
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": STAFF_CHAT_ID,
        "text": formatted_msg,
        "parse_mode": "MarkdownV2"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
    
    if response.status_code == 200:
        return {"status": "dispatched", "target": "Staff Group"}
    else:
        return {"status": "error", "detail": response.text}