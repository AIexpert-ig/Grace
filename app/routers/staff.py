from fastapi import APIRouter, Depends, Request
from app.auth import verify_hmac_signature
from app.templates.notifications import StaffAlertTemplate

router = APIRouter()

@router.post("/escalate", dependencies=[Depends(verify_hmac_signature)])
async def trigger_escalation(data: dict):
    # This is where GRACE routes the data to the Staff Telegram
    formatted_msg = StaffAlertTemplate.format_urgent_escalation(
        data.get('guest_name', 'Unknown'),
        data.get('room_number', 'N/A'),
        data.get('issue', 'General Assistance')
    )
    return {"status": "dispatched", "message_preview": formatted_msg}

@router.post("/ack")
async def acknowledge_task(update: dict):
    # Logic for Redis state management goes here
    return {"status": "claimed", "staff_id": update.get("from", {}).get("id")}