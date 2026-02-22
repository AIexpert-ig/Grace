import os
import json
import time
import hmac
import hashlib
import logging
import asyncio
import re
from pathlib import Path
from typing import Any
from fastapi import FastAPI, WebSocket, Request, HTTPException
from starlette.websockets import WebSocketDisconnect
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

# --- POLICY / TOOL STUBS ---
BOOKING_CONFIRMATION_PATTERN = re.compile(r"\b(booked|confirmed|reserved|see you then)\b", re.IGNORECASE)
PRICING_QUOTE_PATTERN = re.compile(
    r"(\bAED\b|\bUSD\b|\bEUR\b|\bGBP\b|[$€£]|per night|nightly rate|rate is|price is)",
    re.IGNORECASE,
)
BOOKING_KEYWORDS = {"book", "booking", "reserve", "reservation", "appointment", "schedule"}
SPA_KEYWORDS = {"spa", "massage", "facial", "treatment", "salon"}
PRICING_KEYWORDS = {"rate", "rates", "price", "pricing", "cost", "room", "rooms"}

PENDING_BOOKING_MESSAGE = "Thanks — I’m checking availability and will update you shortly with the booking details."
PRICING_REQUEST_MESSAGE = "I can check room rates once I have your check-in date, check-out date, and number of guests."
PRICING_UNAVAILABLE_MESSAGE = "I’m unable to retrieve live rates right now. Please share your dates and guest count, and I can follow up."
STILL_CHECKING_MESSAGE = "I'm still checking that for you and will update you shortly."

SPA_SERVICES = [
    "Swedish massage",
    "Deep tissue massage",
    "Aromatherapy massage",
    "Signature facial",
]

def _emit_event(event_type: str, payload: dict[str, Any] | None = None) -> None:
    data = payload or {}
    logging.getLogger("events").info("EVENT %s %s", event_type, json.dumps(data, ensure_ascii=False))

def _open_staff_ticket(reason: str, user_text: str | None = None, call_id: str | None = None) -> None:
    issue = reason
    if user_text:
        issue = f"{reason} | user_text={user_text}"
    if call_id:
        issue = f"{issue} | call_id={call_id}"
    db = SessionLocal()
    try:
        new_ticket = Escalation(
            guest_name="System",
            room_number="N/A",
            issue=issue,
            status="OPEN",
            sentiment="Neutral",
        )
        db.add(new_ticket)
        db.commit()
    except Exception as exc:
        logging.getLogger("policy").warning("staff_ticket_failed: %s", exc)
    finally:
        db.close()

def spa_list_services() -> dict[str, Any]:
    return {"services": SPA_SERVICES}

def spa_check_availability(service: str, date_time: str) -> dict[str, Any]:
    enabled = os.getenv("SPA_TOOL_ENABLED") == "1"
    return {"service": service, "datetime": date_time, "available": enabled}

def spa_create_booking(name: str, service: str, date_time: str, notes: str | None = None) -> dict[str, Any]:
    if os.getenv("SPA_TOOL_ENABLED") == "1":
        booking_id = f"spa_{int(time.time())}"
        return {"booking_id": booking_id}
    return {"booking_id": None}

def check_room_rates(dates: dict[str, str], guests: int) -> dict[str, Any]:
    if os.getenv("PRICING_TOOL_ENABLED") == "1":
        return {"rates": [{"dates": dates, "guests": guests, "currency": "AED", "amount": 420}]}  # stub
    return {"rates": []}

def _has_keyword(text: str, keywords: set[str]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)

def _extract_dates(text: str) -> dict[str, str | None]:
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if len(dates) >= 2:
        return {"check_in": dates[0], "check_out": dates[1]}
    if len(dates) == 1:
        return {"check_in": dates[0], "check_out": None}
    return {"check_in": None, "check_out": None}

def _extract_guests(text: str) -> int | None:
    match = re.search(r"\b(\d+)\s*(guest|guests|people|adults)\b", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def _extract_spa_service(text: str) -> str | None:
    lowered = text.lower()
    for service in SPA_SERVICES:
        if service.lower() in lowered:
            return service
    return None

def _extract_date_time(text: str) -> str | None:
    date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    time_match = re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", text, re.IGNORECASE)
    if date_match and time_match:
        return f"{date_match.group(0)} {time_match.group(0)}"
    if date_match:
        return date_match.group(0)
    return None

def _apply_response_guards(
    reply: str,
    context: dict[str, Any],
    user_text: str,
    call_id: str | None,
) -> str:
    if BOOKING_CONFIRMATION_PATTERN.search(reply) and not context.get("booking_id"):
        _emit_event("policy.violation", {"type": "booking_confirmation_without_id", "call_id": call_id})
        _open_staff_ticket("policy.violation.booking_confirmation_without_id", user_text, call_id)
        return PENDING_BOOKING_MESSAGE
    if PRICING_QUOTE_PATTERN.search(reply) and not context.get("rates"):
        _emit_event("policy.violation", {"type": "pricing_without_rates", "call_id": call_id})
        _open_staff_ticket("policy.violation.pricing_without_rates", user_text, call_id)
        return PRICING_REQUEST_MESSAGE
    return reply

def _handle_spa_flow(user_text: str, context: dict[str, Any], call_id: str | None) -> str:
    _emit_event("booking.attempted", {"call_id": call_id, "channel": "spa"})
    service = _extract_spa_service(user_text)
    date_time = _extract_date_time(user_text)
    if not service:
        services = ", ".join(SPA_SERVICES)
        return f"We offer {services}. Which service would you like to book?"
    if not date_time:
        return "What date and time would you prefer for the spa appointment?"
    availability = spa_check_availability(service, date_time)
    if not availability.get("available"):
        _emit_event("booking.failed", {"call_id": call_id, "reason": "unavailable"})
        return "I don’t have availability at that time. Would you like a different time?"
    booking = spa_create_booking("Guest", service, date_time, notes=user_text)
    booking_id = booking.get("booking_id")
    if not booking_id:
        _emit_event("booking.failed", {"call_id": call_id, "reason": "missing_booking_id"})
        _open_staff_ticket("booking.failed.missing_booking_id", user_text, call_id)
        return PENDING_BOOKING_MESSAGE
    context["booking_id"] = booking_id
    _emit_event("booking.confirmed", {"call_id": call_id, "booking_id": booking_id})
    return f"Your spa appointment is confirmed. Your booking ID is {booking_id}."

def _handle_pricing_flow(user_text: str, context: dict[str, Any], call_id: str | None) -> str:
    dates = _extract_dates(user_text)
    guests = _extract_guests(user_text)
    if not dates.get("check_in"):
        return "What is your check-in date?"
    if not dates.get("check_out"):
        return "What is your check-out date?"
    if not guests:
        return "How many guests will be staying?"
    rates = check_room_rates({"check_in": dates["check_in"], "check_out": dates["check_out"]}, guests)
    if not rates.get("rates"):
        _open_staff_ticket("pricing.unavailable", user_text, call_id)
        return PRICING_UNAVAILABLE_MESSAGE
    context["rates"] = rates
    rate = rates["rates"][0]
    return f"The rate is {rate['amount']} {rate['currency']} for those dates."

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
    "You are the AI concierge for Courtyard by Marriott Al Barsha in Dubai. "
    "Be concise, polite, and helpful. "
    "If the guest greeting is unclear, ask how you may assist. "
    "Never acknowledge “a request” unless one exists. "
    "Do not repeat yourself."
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
    return "Good afternoon, how may I assist you today?"

def _loop_break_response() -> str:
    return "Good afternoon, how may I assist you today?"

RETELL_CONNECT_GREETING = (
    "Hello, thank you for calling Courtyard By Marriott, Al Barsha. "
    "I am Grace, how may I assist you?"
)

def _retell_debug_marker_enabled() -> bool:
    value = os.getenv("RETELL_DEBUG_MARKER", "").strip().lower()
    return value in {"1", "true", "yes", "on"}

def _retell_state_for(call_id: str) -> dict[str, Any]:
    state = _RETELL_STATE.get(call_id)
    if not state:
        state = {
            "last_assistant": [],
            "last_user": {"text": "", "ts": 0.0},
            "context": {"booking_id": None, "rates": None},
        }
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
async def _retell_ws_handler(websocket: WebSocket, call_id: str | None = None):
    await websocket.accept()
    logger = logging.getLogger("retell")
    start_time = time.time()
    path = getattr(websocket.scope, "get", lambda *_args: None)("path") if hasattr(websocket, "scope") else None
    logger.info("RETELL_WS_ACCEPT call_id=%s path=%s", call_id, path)
    response_counter = 0

    try:
        await websocket.send_json(
            {
                "response_id": 0,
                "content": RETELL_CONNECT_GREETING,
                "content_complete": True,
                "end_call": False,
            }
        )

        while True:
            data = await websocket.receive_json()
            interaction_type = data.get("interaction_type")
            call_id = data.get("call_id") or data.get("conversation_id") or call_id
            response_id_in = data.get("response_id")
            user_text = _get_latest_user_text(data)
            user_preview = (user_text[:40] + "…") if len(user_text) > 40 else user_text
            logger.info(
                "RETELL_WS_RECV call_id=%s path=%s interaction_type=%s response_id=%s preview=%s",
                call_id,
                path,
                interaction_type,
                response_id_in,
                user_preview,
            )

            if interaction_type == "update_only":
                continue

            if interaction_type != "response_required":
                continue

            state = _retell_state_for(call_id or "unknown")
            context = state["context"]
            empty_text = _is_unclear_text(user_text)
            repeated_user = _user_repeated_recent(call_id, user_text)

            if empty_text or repeated_user:
                ai_reply = _clarify_response()
                circuit_breaker = False
            else:
                ai_reply = ""
                if _has_keyword(user_text, SPA_KEYWORDS):
                    ai_reply = _handle_spa_flow(user_text, context, call_id)
                elif _has_keyword(user_text, PRICING_KEYWORDS):
                    ai_reply = _handle_pricing_flow(user_text, context, call_id)
                else:
                    try:
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

                        def _call_model() -> str:
                            model = genai.GenerativeModel("gemini-1.5-flash")
                            response = model.generate_content(messages)
                            return (response.text or "").strip()

                        ai_reply = await asyncio.wait_for(asyncio.to_thread(_call_model), timeout=8.0)
                    except asyncio.TimeoutError:
                        _open_staff_ticket("latency.llm_timeout", user_text, call_id)
                        ai_reply = STILL_CHECKING_MESSAGE
                    except Exception:
                        ai_reply = ""

                if not ai_reply:
                    ai_reply = "I’m experiencing a technical issue. How may I assist you today?"

                last_assistant = state["last_assistant"]
                ai_reply = _apply_response_guards(ai_reply, context, user_text, call_id)
                circuit_breaker = any(ai_reply.strip() == prev for prev in last_assistant[-2:])
                if circuit_breaker:
                    ai_reply = _loop_break_response()

            _record_assistant(call_id or "unknown", ai_reply)

            try:
                resp_id_int = int(response_id_in)
                response_counter = max(response_counter, resp_id_int)
                response_id = resp_id_int
            except Exception:
                response_counter += 1
                response_id = response_counter

            duration_ms = int((time.time() - start_time) * 1000)
            content_to_send = ai_reply
            if _retell_debug_marker_enabled():
                content_to_send = f"GRACE_WS_OK: {content_to_send}"

            logger.info(
                "RETELL_WS_SEND call_id=%s path=%s response_id=%s preview=%s duration_ms=%s",
                call_id,
                path,
                response_id,
                (content_to_send[:40] + "…") if len(content_to_send) > 40 else content_to_send,
                duration_ms,
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
                "content": content_to_send,
                "content_complete": True,
                "end_call": False
            }
            await websocket.send_json(response_event)

    except WebSocketDisconnect as e:
        if e.code == 1000:
            logger.info("RETELL_WS_DISCONNECT call_id=%s code=1000", call_id)
        else:
            logger.warning("RETELL_WS_DISCONNECT call_id=%s code=%s", call_id, e.code)
    except Exception as e:
        logger.exception("RETELL_WS_ERROR %s", e)
        try:
            await websocket.close()
        except Exception:
            pass


@app.websocket("/llm-websocket")
async def websocket_endpoint_root(websocket: WebSocket):
    await _retell_ws_handler(websocket)


@app.websocket("/llm-websocket/{call_id}")
async def websocket_endpoint_with_id(websocket: WebSocket, call_id: str):
    await _retell_ws_handler(websocket, call_id)
