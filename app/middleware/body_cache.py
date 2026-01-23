"""Middleware to cache request body for HMAC verification and Pydantic parsing."""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message


class BodyCacheMiddleware(BaseHTTPMiddleware):
    """Middleware that caches request body for endpoints requiring HMAC verification.
    
    FastAPI's request body stream can only be read once. This middleware
    reads the body once and stores it in request.state so it can be
    accessed multiple times (for HMAC verification and Pydantic parsing).
    """
    
    async def dispatch(self, request: Request, call_next):
        """Cache request body for protected endpoints."""
        # Only cache body for webhook endpoint
        if request.url.path == "/post-call-webhook":
            # Read and cache the body
            body = await request.body()
            request.state.body = body
            request.state.body_str = body.decode('utf-8')
            
            # Create a new message with the cached body
            async def receive() -> Message:
                return {
                    "type": "http.request",
                    "body": body,
                }
            
            request._receive = receive
        
        response = await call_next(request)
        return response
