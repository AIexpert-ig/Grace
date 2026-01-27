import httpx
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request

from app.core.database import get_db
from app.db_models import Escalation
from app.templates.notifications import StaffAlertTemplate
from app.auth import verify_hmac_signature

router = APIRouter()
logger = logging.getLogger(__name__)

# Credentials from Railway Environment
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

@router.get("/dashboard-stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """FEED FOR CLAUDE DASHBOARD: Provides real-time metrics for ExecutiveDashboard.jsx."""
    stmt = select(Escalation).order_by(Escalation.created_at.desc())
    result = await db.execute(stmt)
    alerts = result.scalars().all()
    
    # Calculate response metrics for marketing cards
    res_times = [
        (a.claimed_at - a.created_at).total_seconds() / 60 
        for a in alerts if a.claimed_at
    ]
    avg_res = sum(res_times) / len(res_times) if res_times else 0
    
    staff_stats = {}
    for a in alerts:
        if a.claimed_by: 
            staff_stats[a.claimed_by] = staff_stats.get(a.claimed_by, 0) + 1
    
    return {
        "totalAlerts": len(alerts),
        "avgResponseTime": round(avg_res, 1),
        "resolvedCount": len([a for a in alerts if a.status == "RESOLVED"]),
        "alerts": [
            {
                "room": a.room_number,
                "guest": a.guest_name,
                "issue": a.issue,
                "status": a.status,
                "created_at": a.created_at.isoformat()
            } for a in alerts
        ],
        "topResponders": [
            {"name": k, "claims": v} 
            for k, v in sorted(staff_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
    }

@router.post("/callback")
async def telegram_callback(update: dict, db: AsyncSession = Depends(get_db)):
    """Handles interactive claiming logic (Fixed for Async)."""
    query = update.get("callback_query", update)
    callback_data = query.get("data", "")
    user = query.get("from", {}).get("first_name", "Staff")
    message_id = query.get("message", {}).get("message_id")

    if not callback_data: 
        return {"status": "ignored"}

    # PHASE 1: CLAIM (ack_)
    if callback_data.startswith("ack_"):
        room = callback_data.split("_")[1]
        stmt = select(Escalation).filter(Escalation.room_number == room, Escalation.status == "PENDING")
        res = await db.execute(stmt)
        task = res.scalars().first()

        if task:
            task.status = "IN_PROGRESS"
            task.claimed_by = user
            task.claimed_at = datetime.utcnow()
            await db.commit() # FIXED: MUST AWAIT COMMIT
            
            new_text = f"🚧 <b>In Progress: Room {room}</b>\nClaimed by: {user}"
            markup = {"inline_keyboard": [[{"text": "🏁 Mark Resolved", "callback_data": f"res_{room}"}]]}
            await update_telegram_ui(message_id, new_text, markup)
            return {"status": "claimed"}

    # PHASE 2: RESOLVE (res_)
    if callback_data.startswith("res_"):
        room = callback_data.split("_")[1]
        stmt = select(Escalation).filter(Escalation.room_number == room, Escalation.status == "IN_PROGRESS")
        res = await db.execute(stmt)
        task = res.scalars().first()

        if task:
            task.status = "RESOLVED"
            await db.commit() # FIXED: MUST AWAIT COMMIT
            
            await update_telegram_ui(message_id, f"✅ <b>Resolved: Room {room}</b>\nStaff: {user}", None)
            return {"status": "resolved"}

    return {"status": "unhandled"}

@router.post("/escalate", dependencies=[Depends(verify_hmac_signature)])
async def trigger_escalation(request: Request, db: AsyncSession = Depends(get_db)):
    """Triggers the alert chain and saves to DB."""
    data = await request.json()
    room, guest, issue = data.get('room_number', 'N/A'), data.get('guest_name', 'Unknown'), data.get('issue', 'Assistance')

    # Save to Database
    new_task = Escalation(room_number=room, guest_name=guest, issue=issue, status="PENDING")
    db.add(new_task)
    await db.commit() # FIXED: MUST AWAIT COMMIT

    # Send to Telegram
    msg = StaffAlertTemplate.format_urgent_escalation(guest, room, issue)
    markup = {"inline_keyboard": [[{"text": "✅ Acknowledge & Claim", "callback_data": f"ack_{room}"}]]}
    
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
            json={"chat_id": STAFF_CHAT_ID, "text": msg, "parse_mode": "HTML", "reply_markup": markup}
        )
    
    return {"status": "dispatched"}