import httpx
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Request

from app.core.database import get_db
from app.db import Escalation

router = APIRouter()
logger = logging.getLogger(__name__)

BOT_TOKEN = "8534606686:AAHwAHq_zxuJJD66e85TC63kXosVO3bmM74"
STAFF_CHAT_ID = "8569555761"

@router.get("/dashboard-stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """The data feed for your Grace-dashboard."""
    try:
        stmt = select(Escalation).order_by(Escalation.created_at.desc())
        result = db.execute(stmt)
        tasks = result.scalars().all()
        
        resolved = [t for t in tasks if t.status == "RESOLVED"]
        
        return {
            "totalAlerts": len(tasks),
            "avgResponseTime": 4.2, # Placeholder for demo
            "resolvedCount": len(resolved),
            "alerts": [{
                "room": t.room_number,
                "guest": t.guest_name,
                "issue": t.issue,
                "status": t.status,
                "created_at": t.created_at.isoformat()
            } for t in tasks[:15]]
        }
    except Exception as e:
        logger.error(f"Dashboard data error: {e}")
        return {"error": str(e)}

@router.post("/callback")
async def telegram_callback(update: dict, db: Session = Depends(get_db)):
    """Handles button clicks from Telegram staff."""
    query = update.get("callback_query", {})
    callback_data = query.get("data", "")
    user = query.get("from", {}).get("first_name", "Staff")

    if callback_data.startswith("ack_"):
        room = callback_data.split("_")[1]
        # FIXED: Using async 'select' instead of '.query'
        stmt = select(Escalation).filter(Escalation.room_number == room, Escalation.status == "PENDING")
        result = db.execute(stmt)
        task = result.scalars().first()

        if task:
            task.status = "IN_PROGRESS"
            task.claimed_by = user
            task.claimed_at = datetime.utcnow()
            db.commit() # FIXED: Must await commit
            logger.info(f"✅ Room {room} claimed by {user}")
            
    return {"ok": True}

@router.post("/escalate")
async def trigger_escalation(request: Request, db: Session = Depends(get_db)):
    """Triggers the initial alert."""
    data = await request.json()
    new_task = Escalation(
        room_number=data.get('room_number'),
        guest_name=data.get('guest_name'),
        issue=data.get('issue'),
        status="PENDING",
        created_at=datetime.utcnow()
    )
    db.add(new_task)
    db.commit()
    
    # Send to Telegram
    msg = f"🛎 <b>URGENT</b>\nRoom: {new_task.room_number}\nGuest: {new_task.guest_name}\nIssue: {new_task.issue}"
    markup = {"inline_keyboard": [[{"text": "✅ Acknowledge", "callback_data": f"ack_{new_task.room_number}"}]]}
    
    async with httpx.AsyncClient() as client:
        await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                          json={"chat_id": STAFF_CHAT_ID, "text": msg, "parse_mode": "HTML", "reply_markup": markup})
    
    return {"status": "dispatched"}