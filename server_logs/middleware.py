from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
import uuid

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger):
        super().__init__(app)
        self.logger = logger

    async def dispatch(self, request: Request, call_next):
        req_id = str(uuid.uuid4())[:8]
        start = time.time()
        
        # Capture headers you care about
        headers = {
            "user_agent": request.headers.get("user-agent"),
            "origin": request.headers.get("origin"),
            "content_type": request.headers.get("content-type"),
        }
        
        self.logger.info("request_started",
            req_id=req_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
            **headers
        )
        
        try:
            response = await call_next(request)
            duration = time.time() - start
            
            self.logger.info("request_completed",
                req_id=req_id,
                status=response.status_code,
                duration_ms=round(duration * 1000, 2)
            )
            return response
            
        except Exception as e:
            self.logger.error("request_failed", req_id=req_id, error=str(e))
            raise