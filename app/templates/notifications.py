from datetime import datetime

class StaffAlertTemplate:
    @staticmethod
    def format_urgent_escalation(guest_name: str, room: str, issue: str) -> str:
        return (
            f"🚨 *URGENT ESCALATION*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 *Room:* {room}\n"
            f"👤 *Guest:* {guest_name}\n"
            f"📝 *Issue:* {issue}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Reply /ack to claim this task"
        )