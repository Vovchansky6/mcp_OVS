from fastapi import Request
import uuid
import structlog

logger = structlog.get_logger()


class CorrelationMiddleware:
    """Middleware to add correlation IDs to requests for tracing"""
    
    async def __call__(self, request: Request, call_next):
        # Get correlation ID from header or generate new one
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        
        # Add to request state
        request.state.correlation_id = correlation_id
        
        # Add correlation ID to logger context
        logger = structlog.get_logger()
        logger = logger.bind(correlation_id=correlation_id)
        
        # Store logger in request state for use in other middleware/handlers
        request.state.logger = logger
        
        # Log request start
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client_host=request.client.host if request.client else None
        )
        
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        
        # Log request completion
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code
        )
        
        return response