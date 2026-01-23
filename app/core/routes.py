"""Custom route classes for handling request body caching."""
from typing import Callable

from fastapi import Request, Response
from fastapi.routing import APIRoute


class HMACVerifiedRoute(APIRoute):
    """Custom route that handles HMAC-verified request bodies.
    
    This route ensures that the request body, which has been read
    and verified by the HMAC dependency, can still be accessed
    by the endpoint handler without re-reading the stream.
    """
    
    def get_route_handler(self) -> Callable:
        """Override route handler to use cached body."""
        original_route_handler = super().get_route_handler()
        
        async def custom_route_handler(request: Request) -> Response:
            # If body was cached by HMAC dependency, use it
            if hasattr(request.state, "body"):
                # Create a new receive function that returns cached body
                async def cached_receive() -> dict:
                    return {
                        "type": "http.request",
                        "body": request.state.body,
                    }
                
                # Temporarily replace the receive function
                original_receive = request._receive
                request._receive = cached_receive
                
                try:
                    return await original_route_handler(request)
                finally:
                    # Restore original receive function
                    request._receive = original_receive
            else:
                return await original_route_handler(request)
        
        return custom_route_handler
