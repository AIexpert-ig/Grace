import asyncio
import httpx

# The "Brain" address
API_URL = "https://grace-ai.up.railway.app/staff/escalate"

async def seed_marketing_data():
    demos = [
        {"room": "PH 1", "guest": "Cristiano Ronaldo", "issue": "🚨 Medical Emergency", "urg": "high"},
        {"room": "104", "guest": "Vipul Sharma", "issue": "💧 Major Water Leak", "urg": "high"},
        {"room": "202", "guest": "Sarah Jenkins", "issue": "❄️ AC System Failure", "urg": "medium"},
        {"room": "805", "guest": "Michael Chen", "issue": "🔊 Noise Complaint - Party", "urg": "medium"},
        {"room": "1102", "guest": "Emma Watson", "issue": "📋 Butler Request - VIP", "urg": "low"}
    ]

    print("💎 GRACE AI: Generating Luxury Demo Data...")
    
    async with httpx.AsyncClient() as client:
        for data in demos:
            payload = {
                "room_number": data["room"],
                "guest_name": data["guest"],
                "issue": data["issue"],
                "urgency": data["urg"]
            }
            try:
                await client.post(API_URL, json=payload, timeout=10.0)
                print(f"✅ Dispatched: Room {data['room']} ({data['guest']})")
            except Exception as e:
                print(f"❌ Handshake failed: {e}")
            await asyncio.sleep(1)

    print("\n�� DEMO READY. Check: https://grace-dashboard-production.up.railway.app")

if __name__ == "__main__":
    asyncio.run(seed_marketing_data())
