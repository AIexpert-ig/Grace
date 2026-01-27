import os
import httpx
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Request

from app.auth import verify_hmac_signature
from app.core.database import get_db
from app.db_models import Escalation
from app.templates.notifications import StaffAlertTemplate

router = APIRouter()

# Global Credentials
BOT_TOKEN = "8534606686:AAHwAHq_zxuJJD66e85TC63kXosVO3bmM74"
STAFF_CHAT_ID = "8569555761"

@router.post("/callback")
async def telegram_callback(update: dict, db: Session = Depends(get_db)):
    query = update.get("callback_query", {})
    callback_data = query.get("data", "")
    user = query.get("from", {}).get("first_name", "Staff")
    message_id = query.get("message", {}).get("message_id")

    # --- PHASE 1: CLAIMING THE TASK ---
    if callback_data.startswith("ack_"):
        room = callback_data.split("_")[1]
        escalation = db.query(Escalation).filter(Escalation.room_number == room, Escalation.status == "PENDING").first()

        if escalation:
            escalation.status = "IN_PROGRESS"
            escalation.claimed_by = user
            escalation.claimed_at = datetime.utcnow()
            db.commit()

            # Update UI with a "Mark Resolved" button
            edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
            payload = {
                "chat_id": STAFF_CHAT_ID,
                "message_id": message_id,
                "text": f"🚧 <b>In Progress: Room {room}</b>\nClaimed by: {user}\n<i>Please tap below once the guest is assisted.</i>",
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": [[
                        {"text": "🏁 Mark as Resolved", "callback_data": f"res_{room}"}
                    ]]
                }
            }
            async with httpx.AsyncClient() as client:
                await client.post(edit_url, json=payload)
        return {"status": "claimed"}

    # --- PHASE 2: RESOLVING THE TASK ---
    if callback_data.startswith("res_"):
        room = callback_data.split("_")[1]
        escalation = db.query(Escalation).filter(Escalation.room_number == room, Escalation.status == "IN_PROGRESS").first()

        if escalation:
            escalation.status = "RESOLVED"
            # Logic for final timestamp if you add 'resolved_at' to your model later
            db.commit()

            # Final UI Update (Remove all buttons)
            edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
            payload = {
                "chat_id": STAFF_CHAT_ID,
                "message_id": message_id,
                "text": f"✅ <b>Resolved: Room {room}</b>\nHandled by: {user}\nStatus: <i>Completed</i>",
                "parse_mode": "HTML"
            }
            async with httpx.AsyncClient() as client:
                await client.post(edit_url, json=payload)
        return {"status": "resolved"}
        # 2. TELEGRAM UI UPDATE: Change the message to show the claim
        edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
        edit_payload = {
            "chat_id": STAFF_CHAT_ID,
            "message_id": message_id,
            "text": f"✅ <b>Room {room} Claimed</b>\nStaff: {user}\nStatus: <i>In Progress</i>",
            "parse_mode": "HTML"
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(edit_url, json=edit_payload)
            
        return {"status": "success", "claimed_by": user}
    
    return {"status": "ignored"}

@router.post("/escalate", dependencies=[Depends(verify_hmac_signature)])
async def trigger_escalation(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    room = data.get('room_number', 'N/A')
    guest = data.get('guest_name', 'Unknown')
    
    # 1. CREATE DB ENTRY: Log the initial request
    new_task = Escalation(
        room_number=room,
        guest_name=guest,
        issue=data.get('issue', 'General Assistance'),
        status="PENDING"
    )
    db.add(new_task)
    db.commit()

    # 2. GENERATE UI
    formatted_msg = StaffAlertTemplate.format_urgent_escalation(guest, room, data.get('issue', ''))

    # 3. TRANSMIT TO TELEGRAM
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": STAFF_CHAT_ID,
        "text": formatted_msg,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ Acknowledge & Claim", "callback_data": f"ack_{room}"}
            ]]
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
    
    return {"status": "dispatched" if response.status_code == 200 else "error"}