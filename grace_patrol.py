import sqlalchemy
from sqlalchemy import create_engine, text

# Your specific Railway URL
DB_URL = "postgresql://postgres:JKWfBBHyocHPFkyEdZbjXfTQHMDdBlAV@caboose.proxy.rlwy.net:55545/railway"

try:
    print("🔌 Connecting to Railway...")
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        print("✅ Connection SUCCESS! Reading tickets...")
        
        # Pull the last 5 tickets
        result = conn.execute(text("SELECT id, guest_name, issue, status FROM escalations ORDER BY id DESC LIMIT 5"))
        tickets = result.fetchall()
        
        if not tickets:
            print("📭 The table is empty (No tickets yet).")
        else:
            print(f"📋 Found {len(tickets)} recent tickets:")
            for t in tickets:
                print(f"   🔹 #{t[0]} [{t[3]}] {t[1]}: {t[2]}")

except Exception as e:
    print(f"💥 Connection Failed: {e}")
