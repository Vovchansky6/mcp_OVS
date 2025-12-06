from fastapi import Request, HTTPException
from typing import Dict, Optional
import time
import asyncio
import structlog
import uuid
from datetime import datetime, timedelta

from app.config import settings

logger = structlog.get_logger()


class RateLimitingMiddleware:
    """Rate limiting middleware using Redis-based sliding window"""
    
    def __init__(self):
        self.requests: Dict[str, list] = {}  # In-memory store for demo
        # In production, this would use Redis
    
    async def __call__(self, request: Request, call_next):
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Check rate limit
        if not await self._check_rate_limit(client_id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(settings.rate_limit_window)}
            )
        
        # Record request
        await self._record_request(client_id)
        
        return await call_next(request)
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Try to get user ID from authentication
        if hasattr(request.state, 'user_id'):
            return f"user:{request.state.user_id}"
        
        # Fall back to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return f"ip:{forwarded_for.split(',')[0].strip()}"
        
        return f"ip:{request.client.host}"
    
    async def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client has exceeded rate limit"""
        now = time.time()
        window_start = now - settings.rate_limit_window
        
        # Get client's requests in the window
        client_requests = self.requests.get(client_id, [])
        recent_requests = [req_time for req_time in client_requests if req_time > window_start]
        
        # Check if under limit
        if len(recent_requests) >= settings.rate_limit_requests:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                request_count=len(recent_requests),
                limit=settings.rate_limit_requests
            )
            return False
        
        return True
    
    async def _record_request(self, client_id: str):
        """Record a request for rate limiting"""
        now = time.time()
        
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        self.requests[client_id].append(now)
        
        # Clean up old requests periodically
        if len(self.requests[client_id]) > settings.rate_limit_requests * 2:
            window_start = now - settings.rate_limit_window
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id] 
                if req_time > window_start
            ]


class RateLimitException(Exception):
    """Custom exception for rate limiting"""
    
    def __init__(self, limit: int, window: int, retry_after: int):
        self.limit = limit
        self.window = window
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded: {limit} requests per {window} seconds")