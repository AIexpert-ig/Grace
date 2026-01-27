import httpx
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request

from app.auth import verify_hmac_signature
from app.core.database import get_db
from app.db_models import Escalation
from app.templates.notifications import StaffAlertTemplate

router = APIRouter()

# Global Credentials
BOT_TOKEN = "8534606686:AAHwAHq_zxuJJD66e85TC63kXosVO3bmM74"
STAFF_CHAT_ID = "8569555761"

async def update_telegram_ui(message_id: int, text: str, reply_markup: dict = None):
    """Helper to update the Telegram message state."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": STAFF_CHAT_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)

@router.post("/callback")
async def telegram_callback(update: dict, db: AsyncSession = Depends(get_db)):
    """Handles the full interactive lifecycle using ASYNC patterns."""
    query = update.get("callback_query", update)
    callback_data = query.get("data", "")
    user = query.get("from", {}).get("first_name", "Staff")
    message = query.get("message", {})
    message_id = message.get("message_id")

    if not callback_data:
        return {"status": "ignored"}

    # --- PHASE 1: CLAIMING THE TASK ---
    if callback_data.startswith("ack_"):
        room = callback_data.split("_")[1]
        
        # Async Selection
        stmt = select(Escalation).filter(Escalation.room_number == room, Escalation.status == "PENDING")
        result = await db.execute(stmt)
        task = result.scalars().first()

        if task:
            task.status = "IN_PROGRESS"
            task.claimed_by = user
            task.claimed_at = datetime.utcnow()
            await db.commit() # MUST AWAIT COMMIT

            new_text = f"🚧 <b>In Progress: Room {room}</b>\nClaimed by: {user}\n<i>Assisting guest now...</i>"
            markup = {"inline_keyboard": [[{"text": "🏁 Mark as Resolved", "callback_data": f"res_{room}"}]]}
            await update_telegram_ui(message_id, new_text, markup)
            return {"status": "claimed"}

    # --- PHASE 2: RESOLVING THE TASK ---
    if callback_data.startswith("res_"):
        room = callback_data.split("_")[1]
        
        # Async Selection
        stmt = select(Escalation).filter(Escalation.room_number == room, Escalation.status == "IN_PROGRESS")
        result = await db.execute(stmt)
        task = result.scalars().first()

        if task:
            task.status = "RESOLVED"
            await db.commit() # MUST AWAIT COMMIT

            final_text = f"✅ <b>Resolved: Room {room}</b>\nHandled by: {user}\nStatus: <i>Completed</i>"
            await update_telegram_ui(message_id, final_text)
            return {"status": "resolved"}

    return {"status": "unhandled"}

@router.post("/escalate", dependencies=[Depends(verify_hmac_signature)])
async def trigger_escalation(request: Request, db: AsyncSession = Depends(get_db)):
    """Initial trigger to send the alert to the staff group."""
    import logging
    logger = logging.getLogger(__name__)
    
    data = await request.json()
    room = data.get('room_number', 'N/A')
    guest = data.get('guest_name', 'Unknown')
    issue = data.get('issue', 'General Assistance')

    # 1. Database Entry (Async) - with error handling
    try:
        new_task = Escalation(room_number=room, guest_name=guest, issue=issue, status="PENDING")
        db.add(new_task)
        await db.commit()
        logger.info(f"✅ Escalation saved to DB: Room {room}")
    except Exception as e:
        logger.error(f"❌ Database error: {str(e)}")
        # Continue anyway - send the Telegram message even if DB fails
        await db.rollback()

    # 2. UI Generation
    msg = StaffAlertTemplate.format_urgent_escalation(guest, room, issue)
    markup = {"inline_keyboard": [[{"text": "✅ Acknowledge & Claim", "callback_data": f"ack_{room}"}]]}

    # 3. Transmission
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": STAFF_CHAT_ID, "text": msg, "parse_mode": "HTML", "reply_markup": markup}

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
    
    return {"status": "dispatched" if response.status_code == 200 else "error"}