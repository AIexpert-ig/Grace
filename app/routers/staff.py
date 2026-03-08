import logging
from datetime import datetime, timezone
from html import escape

import httpx
from fastapi import APIRouter, Depends
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db
from app.models import Escalation

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/dashboard-stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """The data feed for your Grace-dashboard."""
    try:
        result = await db.execute(select(Escalation).order_by(Escalation.created_at.desc()))
        tasks = result.scalars().all()

        resolved = [t for t in tasks if t.status == "RESOLVED"]

        return {
            "totalAlerts": len(tasks),
            "avgResponseTime": 4.2,
            "resolvedCount": len(resolved),
            "alerts": [
                {
                    "room": t.room_number,
                    "guest": t.guest_name,
                    "issue": t.issue,
                    "status": t.status,
                    "created_at": t.created_at.isoformat(),
                }
                for t in tasks[:15]
            ],
        }
    except Exception as e:
        logger.error("Dashboard data error: %s", e)
        return {"error": str(e)}


@router.post("/callback")
async def telegram_callback(update: dict, db: AsyncSession = Depends(get_db)):
    """Handles button clicks from Telegram staff."""
    query = update.get("callback_query", {})
    callback_data = query.get("data", "")
    user = query.get("from", {}).get("first_name", "Staff")

    if callback_data.startswith("ack_"):
        room = callback_data.split("_")[1]
        result = await db.execute(
            select(Escalation).where(
                Escalation.room_number == room,
                Escalation.status == "PENDING",
            )
        )
        task = result.scalars().first()

        if task:
            task.status = "IN_PROGRESS"
            task.claimed_by = user
            task.claimed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("Room %s claimed by %s", room, user)

    return {"ok": True}


@router.post("/escalate")
async def trigger_escalation(request: Request, db: AsyncSession = Depends(get_db)):
    """Triggers the initial alert."""
    data = await request.json()
    new_task = Escalation(
        room_number=data.get("room_number"),
        guest_name=data.get("guest_name"),
        issue=data.get("issue"),
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_task)
    await db.commit()

    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        # HTML-escape all user-supplied fields before interpolating into HTML message
        room = escape(str(new_task.room_number or ""))
        guest = escape(str(new_task.guest_name or ""))
        issue = escape(str(new_task.issue or ""))
        msg = f"🛎 <b>URGENT</b>\nRoom: {room}\nGuest: {guest}\nIssue: {issue}"
        markup = {
            "inline_keyboard": [
                [{"text": "✅ Acknowledge", "callback_data": f"ack_{new_task.room_number}"}]
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": settings.TELEGRAM_CHAT_ID,
                        "text": msg,
                        "parse_mode": "HTML",
                        "reply_markup": markup,
                    },
                )
        except Exception as exc:
            logger.warning("telegram_send_failed: %s", exc)

    return {"status": "dispatched"}
