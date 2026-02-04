import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 SYSTEM STARTUP: Grace AI is coming online...")
    yield
    logger.info("🛑 SYSTEM SHUTDOWN")


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if os.path.exists("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    if os.path.exists("app/static/index.html"):
        return FileResponse("app/static/index.html")
    return {"status": "Grace AI Online", "version": "v33-nuclear-fix"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/llm-websocket/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    await websocket.accept()
    logger.info("📞 Connected: %s", call_id)
    try:
        await websocket.send_json({
            "response_type": "response",
            "response_id": 0,
            "content": "Hello, this is Grace. I am fully operational.",
            "content_complete": True,
            "end_call": False,
        })
        while True:
            data = await websocket.receive_json()
            logger.info("Received: %s", data)
    except WebSocketDisconnect:
        logger.info("📞 Disconnected")
