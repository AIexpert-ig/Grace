from datetime import datetime

class StaffAlertTemplate:
    @staticmethod
    def format_urgent_escalation(guest_name: str, room: str, issue: str) -> str:
        return (
            f"🚨 <b>URGENT ESCALATION</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>Room:</b> {room}\n"
            f"👤 <b>Guest:</b> {guest_name}\n"
            f"📝 <b>Issue:</b> {issue}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Reply /ack to claim this task"
        )