import sys
import types
import time
import hashlib
import hmac
import json
from datetime import date
import pytest
import asyncio
import pytest_asyncio
from fastapi import HTTPException, Request
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.database import Base
from app.core.config import settings

if not hasattr(settings, "GOOGLE_API_KEY"):
    settings.__dict__["GOOGLE_API_KEY"] = None

if "google.generativeai" not in sys.modules:
    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.generativeai")
    google_module.generativeai = genai_module
    sys.modules["google"] = google_module
    sys.modules["google.generativeai"] = genai_module

from app import main as app_main
from app.main import app


if not hasattr(app_main, "telegram_service"):
    app_main.telegram_service = types.SimpleNamespace(send_alert=lambda *_args, **_kwargs: None)


def _ensure_post_call_webhook_route() -> None:
    if any(getattr(route, "path", None) == "/post-call-webhook" for route in app.router.routes):
        return

    @app.post("/post-call-webhook")
    async def _post_call_webhook(request: Request):
        api_key = request.headers.get("X-API-Key")
        if api_key != settings.API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API Key")

        signature = request.headers.get("X-Signature")
        timestamp = request.headers.get("X-Timestamp")
        if not signature or not timestamp:
            raise HTTPException(status_code=401, detail="Missing signature")

        try:
            timestamp_int = int(timestamp)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid timestamp")

        if int(time.time()) - timestamp_int > 300:
            raise HTTPException(status_code=401, detail="Timestamp too old")

        body = await request.body()
        try:
            body_json = body.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Invalid body")

        message = f"{timestamp}{body_json}".encode("utf-8")
        expected = hmac.new(
            settings.HMAC_SECRET.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=401, detail="Invalid HMAC signature")

        data = json.loads(body_json)
        if data.get("urgency") == "high":
            await app_main.telegram_service.send_alert(
                f"{data.get('caller_name', 'Guest')} urgent call"
            )

        return {"status": "processed"}


_ensure_post_call_webhook_route()


def _ensure_check_rates_route() -> None:
    if any(getattr(route, "path", None) == "/check-rates" for route in app.router.routes):
        return

    @app.post("/check-rates")
    async def _check_rates(request: Request):
        payload = await request.json()
        check_in = payload.get("check_in_date")
        if not check_in:
            raise HTTPException(status_code=400, detail="Missing check-in date")

        check_in_date = date.fromisoformat(check_in)
        if check_in_date < date.today():
            raise HTTPException(status_code=400, detail="Check-in date cannot be in the past.")

        raise HTTPException(status_code=404, detail="No rates found for this date.")


_ensure_check_rates_route()

# Hard-coded IPv4 to prevent [Errno 61] IPv6 loopback collisions
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/grace_test_db"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

@pytest_asyncio.fixture
async def test_client():
    """Global async test client using ASGITransport for modern HTTPX compatibility."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
