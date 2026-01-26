# app/routers/staff.py
from fastapi import APIRouter, Depends
from app.auth import verify_hmac_signature
from app.templates.notifications import StaffAlertTemplate # Use the template we moved

router = APIRouter()

@router.post("/escalate", dependencies=[Depends(verify_hmac_signature)])
async def trigger_escalation(data: dict):
    # This turns the raw data into a world-class alert
    formatted_msg = StaffAlertTemplate.format_urgent_escalation(
        data.get('guest_name', 'Unknown'),
        data.get('room_number', 'N/A'),
        data.get('issue', 'General Assistance')
    )
    return {
        "status": "success", 
        "message_preview": formatted_msg # Now returns the high-end UI
    }