from .llm import analyze_escalation
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from .auth import verify_hmac_signature

logger = logging.getLogger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # FORCE SYNC V14.0
    print("🚀 DUBAI-SYNC-V14: SYSTEM STARTING") # Standard print to force stdout
    logger.info("🚀 GRACE AI Infrastructure Online [V14.0-DUBAI-MASTER]")
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/staff/escalate")
async def escalate(request: Request, authenticated: bool = Depends(verify_hmac_signature)):
    # 1. Get the raw data
    data = await request.json()
    guest = data.get("guest_name", "Unknown")
    issue = data.get("issue", "No issue provided")

    # 2. ASK THE BRAIN
    logger.info(f"🧠 AI Analyzing issue for {guest}...")
    ai_result = await analyze_escalation(guest, issue)
    
    # 3. Log the Intelligence (This proves it works)
    logger.info("------------------------------------------------")
    logger.info(f"🤖 AI VERDICT: {ai_result['priority']}")
    logger.info(f"📝 PLAN: {ai_result['action_plan']}")
    logger.info("------------------------------------------------")

    # 4. Save to DB (We append the plan to the issue for now so you can see it)
    # TODO: In Phase 3 we will create dedicated columns for this.
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            # We append the AI plan to the issue text so it saves in the current DB schema
            enhanced_issue = f"{issue} || [AI PLAN: {ai_result['action_plan']}]"
            
            await conn.execute(text(
                "INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"
            ), {
                "g": guest,
                "r": data.get("room_number"),
                "i": enhanced_issue,
                "s": "OPEN",
                "sent": ai_result['sentiment'] # Using AI sentiment instead of raw
            })
    except Exception as e:
        logger.error(f"DB Error: {e}")
        return {"status": "error", "message": str(e)}

    return {
        "status": "dispatched", 
        "ai_analysis": ai_result
    }
