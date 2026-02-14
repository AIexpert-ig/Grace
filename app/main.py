import os
import json
import time
import hmac
import hashlib
import logging
from pathlib import Path
from typing import Any
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import google.generativeai as genai
import httpx

# --- CONFIGURATION ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/railway")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
def _get_admin_token() -> str | None:
    return os.getenv("ADMIN_TOKEN")

def _get_make_webhook_url() -> str | None:
    return os.getenv("MAKE_WEBHOOK_URL")

def _get_make_signing_secret() -> str | None:
    return os.getenv("MAKE_SIGNING_SECRET")

def _get_webhook_tolerance() -> int:
    return int(os.getenv("WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS", "300"))

# --- DATABASE SETUP ---
Base = declarative_base()

class Escalation(Base):
    __tablename__ = "escalations"
    id = Column(Integer, primary_key=True, index=True)
    guest_name = Column(String, default="Unknown Guest")
    room_number = Column(String, default="Unknown")
    issue = Column(Text)
    status = Column(String, default="OPEN")
    sentiment = Column(String, default="Neutral")
    created_at = Column(DateTime, default=datetime.utcnow)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- FASTAPI APP ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_PATH = STATIC_DIR / "index.html"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- RETELL CUSTOM LLM CONFIG ---
SYSTEM_PROMPT = (
    "You are Grace, the concierge for Courtyard by Marriott Al Barsha. "
    "Be concise, polite, and helpful. "
    "If the user is greeting or unclear, ask a single clarifying question. "
    "Never claim an action was done unless confirmed. "
    "Collect room number if needed. Escalate if the request is critical or safety-related. "
    "If prior assistant message equals the candidate response, do NOT repeat; ask for clarification. "
    "No hallucinations."
)

# Rolling state keyed by call_id for loop prevention
_RETELL_STATE: dict[str, dict[str, Any]] = {}

def _get_latest_user_text(payload: dict) -> str:
    transcript = payload.get("transcript")
    if isinstance(transcript, list):
        for item in reversed(transcript):
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role == "user" and isinstance(content, str) and content.strip():
                return content.strip()
    text = payload.get("user_text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ""

def _is_unclear_text(text: str) -> bool:
    if not text or not text.strip():
        return True
    lowered = text.strip().lower()
    return lowered in {"hello", "hello?", "hi", "hi?", "hey", "hey?"}

def _clarify_response() -> str:
    return "I can hear you. How can I help—booking, directions, or a request for your room?"

def _loop_break_response() -> str:
    return "I may be missing your request. Tell me what you want to do (e.g., extend stay, late checkout, extra towels)."

def _retell_state_for(call_id: str) -> dict[str, Any]:
    state = _RETELL_STATE.get(call_id)
    if not state:
        state = {"last_assistant": [], "last_user": {"text": "", "ts": 0.0}}
        _RETELL_STATE[call_id] = state
    return state

def _record_assistant(call_id: str, response: str) -> None:
    state = _retell_state_for(call_id)
    history = state["last_assistant"]
    history.append(response.strip())
    if len(history) > 3:
        del history[:-3]

def _user_repeated_recent(call_id: str, text: str) -> bool:
    state = _retell_state_for(call_id)
    last = state["last_user"]
    now = time.time()
    if last["text"] == text and (now - last["ts"]) <= 10:
        return True
    state["last_user"] = {"text": text, "ts": now}
    return False

def _auth_error(required_header: str, reason: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": "unauthorized", "required_header": required_header, "reason": reason},
    )

def _get_httpx_client():
    return httpx.AsyncClient()

def _verify_hmac(raw_body: bytes, timestamp: str | None, signature: str | None, secret: str) -> tuple[bool, str]:
    if not timestamp or not signature:
        return False, "missing_signature_headers"
    try:
        ts_int = int(timestamp)
    except (TypeError, ValueError):
        return False, "timestamp_invalid_or_expired"
    if abs(int(time.time()) - ts_int) > _get_webhook_tolerance():
        return False, "timestamp_invalid_or_expired"
    if signature.lower().startswith("sha256="):
        signature = signature.split("=", 1)[1]
    message = timestamp.encode() + b"." + raw_body
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False, "signature_mismatch"
    return True, "ok"
# --- ROUTES ---

@app.get("/")
async def read_root():
    with INDEX_PATH.open("r", encoding="utf-8") as handle:
        content = handle.read()
    build_sha = os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GITHUB_SHA") or "unknown"
    marker = f"DEPLOY_MARKER=2077_UI_V2_{build_sha[:7]}"
    content = content.replace("__DEPLOY_MARKER__", marker)
    return HTMLResponse(
        content=content,
        status_code=200,
        headers={
            "Cache-Control": "no-store, max-age=0, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Grace Hotel AI"}

@app.get("/admin/ping")
def admin_ping(request: Request):
    header = request.headers.get("X-Admin-Token")
    admin_token = _get_admin_token()
    if not admin_token:
        return JSONResponse(status_code=503, content={"error": "admin_token_missing", "required_header": "X-Admin-Token"})
    if not header or not hmac.compare_digest(header, admin_token):
        return _auth_error("X-Admin-Token", "invalid_admin_token")
    return {"status": "ok"}

# --- DASHBOARD API ---

@app.get("/staff/recent-tickets")
def get_recent_tickets():
    db = SessionLocal()
    try:
        tickets = db.query(Escalation).order_by(Escalation.created_at.desc()).limit(20).all()
        return [
            {
                "id": t.id,
                "guest_name": t.guest_name,
                "room_number": t.room_number,
                "issue": t.issue,
                "status": t.status,
                "sentiment": t.sentiment,
                "created_at": t.created_at.isoformat()
            }
            for t in tickets
        ]
    finally:
        db.close()

@app.get("/staff/dashboard-stats")
def get_stats():
    db = SessionLocal()
    try:
        total = db.query(Escalation).count()
        open_tickets = db.query(Escalation).filter(Escalation.status == "OPEN").count()
        return {
            "total_tickets": total,
            "open_tickets": open_tickets,
            "sentiment_score": 98 
        }
    finally:
        db.close()

@app.post("/staff/escalate")
async def create_ticket(request: Request):
    data = await request.json()
    db = SessionLocal()
    try:
        new_ticket = Escalation(
            guest_name=data.get("guest_name", "Test Guest"),
            room_number=data.get("room_number", "101"),
            issue=data.get("issue", "Test Issue"),
            status="OPEN",
            sentiment=data.get("sentiment", "Neutral")
        )
        db.add(new_ticket)
        db.commit()
        return {"status": "Ticket Created"}
    finally:
        db.close()

@app.delete("/staff/tickets/{ticket_id}")
def delete_ticket(ticket_id: int):
    db = SessionLocal()
    try:
        ticket = db.query(Escalation).filter(Escalation.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        db.delete(ticket)
        db.commit()
        return {"status": "deleted", "id": ticket_id}
    finally:
        db.close()

@app.post("/integrations/make/trigger")
async def make_trigger(request: Request):
    raw_body = await request.body()
    admin_header = request.headers.get("X-Admin-Token")
    admin_token = _get_admin_token()
    make_secret = _get_make_signing_secret()
    make_webhook_url = _get_make_webhook_url()

    if admin_token and admin_header and hmac.compare_digest(admin_header, admin_token):
        pass
    elif make_secret:
        ok, reason = _verify_hmac(
            raw_body=raw_body,
            timestamp=request.headers.get("X-Signature-Timestamp"),
            signature=request.headers.get("X-Signature"),
            secret=make_secret,
        )
        if not ok:
            return _auth_error("X-Signature", reason)
    else:
        return _auth_error("X-Admin-Token", "missing_admin_token")

    if not make_webhook_url:
        return JSONResponse(status_code=503, content={"error": "make_webhook_url_missing"})

    try:
        payload = json.loads(raw_body)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_envelope"})

    async with _get_httpx_client() as client:
        resp = await client.post(
            make_webhook_url,
            json=payload,
            headers={"X-Correlation-Id": payload.get("correlation_id", "")},
            timeout=10,
        )
    if resp.status_code >= 400:
        return JSONResponse(status_code=502, content={"error": "make_webhook_failed"})
    return JSONResponse(status_code=200, content={"status": "sent", "correlation_id": payload.get("correlation_id")})

# --- WEBHOOK ---
@app.post("/webhook")
async def handle_webhook(request: Request):
    payload = await request.json()
    print(f"📝 WEBHOOK RECEIVED: {json.dumps(payload)}")
    return {"received": True}

# --- VOICE BRAIN (WEBSOCKET) ---
@app.websocket("/llm-websocket/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    await websocket.accept()
    logger = logging.getLogger("retell")
    logger.info("retell_ws_connected call_id=%s", call_id)
    response_counter = 0

    try:
        await websocket.send_json(
            {
                "response_id": 0,
                "content": "",
                "content_complete": True,
                "end_call": False,
            }
        )

        while True:
            data = await websocket.receive_json()
            interaction_type = data.get("interaction_type")
            user_text = _get_latest_user_text(data)
            user_preview = (user_text[:32] + "…") if len(user_text) > 32 else user_text
            logger.info(
                "retell_ws_in call_id=%s interaction_type=%s user_text=%s",
                call_id,
                interaction_type,
                user_preview,
            )

            if interaction_type == "update_only":
                continue

            if interaction_type != "response_required":
                continue

            state = _retell_state_for(call_id)
            empty_text = _is_unclear_text(user_text)
            repeated_user = _user_repeated_recent(call_id, user_text)

            if empty_text or repeated_user:
                ai_reply = "Hello! How can I help you today at Courtyard by Marriott Al Barsha?"
                circuit_breaker = False
            else:
                ai_reply = ""
                try:
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    transcript = data.get("transcript")
                    history = []
                    if isinstance(transcript, list):
                        for item in transcript[-6:]:
                            if not isinstance(item, dict):
                                continue
                            role = item.get("role")
                            content = item.get("content")
                            if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
                                history.append({"role": role, "content": content.strip()})
                    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
                    if not messages or messages[-1].get("role") != "user":
                        messages.append({"role": "user", "content": user_text})
                    response = model.generate_content(messages)
                    ai_reply = (response.text or "").strip()
                except Exception:
                    ai_reply = ""

                if not ai_reply:
                    ai_reply = "I’m having a technical issue. How can I help you today?"

                last_assistant = state["last_assistant"]
                circuit_breaker = any(ai_reply.strip() == prev for prev in last_assistant[-2:])
                if circuit_breaker:
                    ai_reply = _loop_break_response()

            _record_assistant(call_id, ai_reply)

            resp_id = data.get("response_id")
            try:
                resp_id_int = int(resp_id)
                response_counter = max(response_counter, resp_id_int)
                response_id = resp_id_int
            except Exception:
                response_counter += 1
                response_id = response_counter

            logger.info(
                "retell_ws_out call_id=%s response_id=%s empty=%s loop_break=%s",
                call_id,
                response_id,
                empty_text,
                circuit_breaker,
            )

            # SAVE TO DB LOGIC
            if len(user_text) > 5:
                db = SessionLocal()
                try:
                    new_ticket = Escalation(
                        guest_name="Voice Call Guest",
                        room_number="Unknown",
                        issue=user_text,
                        status="OPEN",
                        sentiment="Neutral"
                    )
                    db.add(new_ticket)
                    db.commit()
                except Exception:
                    pass
                finally:
                    db.close()

            response_event = {
                "response_id": response_id,
                "content": ai_reply,
                "content_complete": True,
                "end_call": False
            }
            await websocket.send_json(response_event)

    except Exception as e:
        logger.info("retell_ws_closed call_id=%s error=%s", call_id, e)
