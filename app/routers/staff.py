import os
import httpx
from fastapi import APIRouter, Depends, Request
from app.auth import verify_hmac_signature
from app.templates.notifications import StaffAlertTemplate

router = APIRouter()

# Global Credentials (Hardcoded for your specific bot)
BOT_TOKEN = "8534606686:AAHwAHq_zxuJJD66e85TC63kXosVO3bmM74"
STAFF_CHAT_ID = "8569555761"

@router.post("/callback")
async def telegram_callback(update: dict, db: Session = Depends(get_db)):
    """Handles button clicks and persists the 'Claim' in the DB"""
    query = update.get("callback_query", {})
    callback_data = query.get("data", "")
    user = query.get("from", {}).get("first_name", "Staff Member")
    message_id = query.get("message", {}).get("message_id")

    if callback_data.startswith("ack_"):
        room = callback_data.split("_")[1]
        
        # 1. Update DB: Find the most recent active request for this room
        # Note: You would typically have an 'Escalation' model in app/db_models.py
        # For now, we simulate the update logic:
        print(f"DEBUG: Updating DB for Room {room}. Claimed by {user}.")
        
        # 2. Update the Telegram Message UI
        edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
        edit_payload = {
            "chat_id": STAFF_CHAT_ID,
            "message_id": message_id,
            "text": f"✅ <b>Room {room} Claimed</b>\nStaff: {user}\nStatus: <i>In Progress</i>",
            "parse_mode": "HTML"
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(edit_url, json=edit_payload)
            
        return {"status": "success", "claimed_by": user, "room": room}
    
    return {"status": "ignored"}

@router.post("/escalate", dependencies=[Depends(verify_hmac_signature)])
async def trigger_escalation(request: Request):
    data = await request.json()
    
    # 1. Generate the world-class UI message
    formatted_msg = StaffAlertTemplate.format_urgent_escalation(
        data.get('guest_name', 'Unknown Guest'),
        data.get('room_number', 'N/A'),
        data.get('issue', 'General Assistance')
    )

    # 2. Transmit to Telegram with an Interactive Button
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": STAFF_CHAT_ID,
        "text": formatted_msg,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ Acknowledge & Claim", "callback_data": f"ack_{data.get('room_number')}"}
            ]]
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
    
    if response.status_code == 200:
        return {"status": "dispatched", "target": "Staff Group"}
    else:
        return {"status": "error", "detail": response.text}