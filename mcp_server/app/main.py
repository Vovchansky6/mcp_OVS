from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import structlog
import time
import uuid
from typing import Dict, Any

from app.config import settings
from app.api.v1 import tools, resources, health, admin
from app.middleware.auth import AuthMiddleware
from app.middleware.rate_limiting import RateLimitingMiddleware
from app.middleware.correlation import CorrelationMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.exceptions import MCPException, ValidationException, RateLimitException
from app.core.database import init_db, close_db, get_db
from app.core.redis_client import redis_client


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting MCP Business AI Server", version=settings.app_version)

    # Initialize services
    try:
        await init_db()
        await redis_client.connect()
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise

    yield

    await redis_client.disconnect()
    await close_db()
    logger.info("Shutting down MCP Business AI Server")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Enterprise-grade MCP server for business AI transformation",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure appropriately for production
)

# Custom middleware (order matters)
app.add_middleware(CorrelationMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitingMiddleware)
app.add_middleware(AuthMiddleware)


# Exception handlers
@app.exception_handler(MCPException)
async def mcp_exception_handler(request: Request, exc: MCPException):
    logger.error(
        "MCP exception occurred",
        error_code=exc.error_code,
        message=exc.message,
        correlation_id=getattr(request.state, "correlation_id", None)
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )


@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException):
    logger.warning(
        "Validation error",
        field=exc.field,
        message=exc.message,
        correlation_id=getattr(request.state, "correlation_id", None)
    )
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": exc.message,
                "field": exc.field
            }
        }
    )


@app.exception_handler(RateLimitException)
async def rate_limit_exception_handler(request: Request, exc: RateLimitException):
    logger.warning(
        "Rate limit exceeded",
        limit=exc.limit,
        window=exc.window,
        correlation_id=getattr(request.state, "correlation_id", None)
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded. Max {exc.limit} requests per {exc.window} seconds.",
                "retry_after": exc.retry_after
            }
        },
        headers={"Retry-After": str(exc.retry_after)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unexpected error occurred",
        error=str(exc),
        type=type(exc).__name__,
        correlation_id=getattr(request.state, "correlation_id", None)
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred"
            }
        }
    )


# Include routers
app.include_router(
    tools.router,
    prefix="/api/v1/tools",
    tags=["tools"]
)

app.include_router(
    resources.router,
    prefix="/api/v1/resources", 
    tags=["resources"]
)

app.include_router(
    health.router,
    prefix="/api/v1/health",
    tags=["health"]
)

app.include_router(
    admin.router,
    prefix="/api/v1/admin",
    tags=["admin"]
)


# Root endpoint
@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "timestamp": time.time()
    }


# MCP Protocol endpoint
@app.post("/mcp")
async def mcp_endpoint(request: Request, message: Dict[str, Any]):
    """Main MCP protocol endpoint"""
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    
    logger.info(
        "MCP request received",
        method=message.get("method"),
        correlation_id=correlation_id
    )
    
    try:
        # Handle different MCP methods
        method = message.get("method")
        
        if method == "initialize":
            return await handle_initialize(message, correlation_id)
        elif method == "tools/list":
            return await handle_tools_list(message, correlation_id)
        elif method == "tools/call":
            return await handle_tools_call(message, correlation_id)
        elif method == "resources/list":
            return await handle_resources_list(message, correlation_id)
        elif method == "resources/read":
            return await handle_resources_read(message, correlation_id)
        else:
            raise MCPException(
                error_code="METHOD_NOT_FOUND",
                message=f"Method '{method}' not found",
                status_code=404
            )
            
    except Exception as e:
        logger.error(
            "Error processing MCP request",
            method=method,
            error=str(e),
            correlation_id=correlation_id
        )
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32603,
                "message": "Internal error"
            }
        }


async def handle_initialize(message: Dict[str, Any], correlation_id: str):
    """Handle MCP initialization"""
    logger.info("MCP initialization", correlation_id=correlation_id)
    
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {}
            },
            "serverInfo": {
                "name": settings.app_name,
                "version": settings.app_version
            }
        }
    }


async def handle_tools_list(message: Dict[str, Any], correlation_id: str):
    """Handle tools list request"""
    # This would be implemented to return available tools
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {
            "tools": []
        }
    }


async def handle_tools_call(message: Dict[str, Any], correlation_id: str):
    """Handle tool execution request"""
    # This would be implemented to execute tools
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {
            "content": [],
            "isError": False
        }
    }


async def handle_resources_list(message: Dict[str, Any], correlation_id: str):
    """Handle resources list request"""
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {
            "resources": []
        }
    }


async def handle_resources_read(message: Dict[str, Any], correlation_id: str):
    """Handle resource read request"""
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {
            "contents": []
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers
    )