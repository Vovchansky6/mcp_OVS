from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import structlog
import time
import uuid
from typing import Dict, Any

from app.config import settings
from app.exceptions import MCPException, ValidationException, RateLimitException
from app.core.database import init_db, close_db
from app.core.redis_client import redis_client

# ------------------------ ЛОГИРОВАНИЕ ------------------------ #

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
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# ------------------------ LIFESPAN ------------------------ #


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MCP Business AI Server", version=settings.app_version)

    # DB и Redis считаем опциональными – если их нет локально, просто логируем и идём дальше
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning("Failed to initialize database, continuing without DB", error=str(e))

    try:
        await redis_client.connect()
        logger.info("Redis client connected")
    except Exception as e:
        logger.warning("Failed to connect Redis, continuing without Redis", error=str(e))

    yield

    try:
        await redis_client.disconnect()
        logger.info("Redis client disconnected")
    except Exception as e:
        logger.warning("Failed to disconnect Redis", error=str(e))

    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.warning("Failed to close database", error=str(e))

    logger.info("Shutting down MCP Business AI Server")

# ------------------------ APP ------------------------ #

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="MCP server for business AI transformation",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS / Trusted hosts
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
)

# ------------------------ SAFE MIDDLEWARES ------------------------ #

def _safe_add_middleware(mw_name: str, import_path: str, cls_name: str):
    """
    Пытаемся подключить middleware. Если нет зависимостей (jwt, opentelemetry и т.п.) —
    не валим всё приложение, а просто логируем предупреждение.
    """
    try:
        module = __import__(import_path, fromlist=[cls_name])
        cls = getattr(module, cls_name)
        app.add_middleware(cls)
        logger.info("Middleware enabled", middleware=mw_name)
    except Exception as e:
        logger.warning("Middleware disabled", middleware=mw_name, error=str(e))


# Эти middlewares зависят от jwt, opentelemetry и прочего. Подключаем по возможности.
_safe_add_middleware("auth", "app.middleware.auth", "AuthMiddleware")
_safe_add_middleware("rate_limiting", "app.middleware.rate_limiting", "RateLimitingMiddleware")
_safe_add_middleware("correlation", "app.middleware.correlation", "CorrelationMiddleware")
_safe_add_middleware("metrics", "app.middleware.metrics", "MetricsMiddleware")

# ------------------------ ROUTERS ------------------------ #

# Обязательный роутер – tools (инструменты MCP)
from app.api.v1 import tools

app.include_router(tools.router, prefix="/api/v1/tools", tags=["tools"])


def _safe_include_router(module_path: str, tag: str, prefix: str):
    """
    Подключаем роутер, если модуль есть.
    Если нет (resource_manager, agent_system и т.п.) — логируем и идём дальше.
    """
    try:
        module = __import__(module_path, fromlist=["router"])
        router = getattr(module, "router")
        app.include_router(router, prefix=prefix, tags=[tag])
        logger.info("Router enabled", module=module_path, prefix=prefix)
    except Exception as e:
        logger.warning("Router disabled", module=module_path, error=str(e))


# Необязательные роутеры – падают, если нет resource_manager / agent_system.
_safe_include_router("app.api.v1.resources", "resources", "/api/v1/resources")
_safe_include_router("app.api.v1.admin", "admin", "/api/v1/admin")

# ------------------------ ЛОГИРОВАНИЕ ЗАПРОСОВ ------------------------ #


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())

    logger.info(
        "Request started",
        method=request.method,
        path=request.url.path,
        correlation_id=correlation_id,
    )

    try:
        response: Response = await call_next(request)
    except Exception as e:
        logger.error(
            "Unhandled exception during request",
            method=request.method,
            path=request.url.path,
            error=str(e),
            correlation_id=correlation_id,
        )
        raise

    process_time = time.time() - start_time
    logger.info(
        "Request completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(process_time * 1000, 2),
        correlation_id=correlation_id,
    )

    return response

# ------------------------ HANDLERS EXCEPTIONS ------------------------ #


@app.exception_handler(MCPException)
async def mcp_exception_handler(request: Request, exc: MCPException):
    logger.error(
        "MCP exception occurred",
        error_code=exc.error_code,
        message=exc.message,
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException):
    logger.warning(
        "Validation error",
        field=exc.field,
        message=exc.message,
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": exc.message,
                "field": exc.field,
            }
        },
    )


@app.exception_handler(RateLimitException)
async def rate_limit_exception_handler(request: Request, exc: RateLimitException):
    logger.warning(
        "Rate limit exceeded",
        limit=exc.limit,
        window=exc.window,
        retry_after=exc.retry_after,
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests",
                "details": {
                    "limit": exc.limit,
                    "window": exc.window,
                    "retry_after": exc.retry_after,
                },
            }
        },
        headers={"Retry-After": str(exc.retry_after)},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
            }
        },
    )

# ------------------------ HEALTH + MCP ------------------------ #


@app.get("/health", tags=["health"])
@app.get("/api/v1/health", tags=["health"])
async def health_check():
    """Простой health-эндпоинт без обращения к БД/Redis."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "app": settings.app_name,
    }


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    Единая точка входа MCP (JSON-RPC).
    Поддерживает методы:
      - initialize
      - tools/list
      - tools/call
      - resources/list
      - resources/read
    """
    try:
        message = await request.json()
    except Exception as e:
        logger.error("Failed to parse MCP request", error=str(e))
        raise MCPException(
            "Invalid JSON-RPC request",
            error_code="INVALID_REQUEST",
            status_code=400,
        )

    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    method = message.get("method")

    try:
        if not method:
            raise MCPException(
                "Missing method in MCP request",
                error_code="INVALID_REQUEST",
                status_code=400,
            )

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
                status_code=404,
            )

    except MCPException as e:
        logger.error(
            "Error processing MCP request",
            method=method,
            error=e.message,
            correlation_id=correlation_id,
        )
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32000,
                "message": e.message,
            },
        }
    except Exception as e:
        logger.error(
            "Error processing MCP request",
            method=method,
            error=str(e),
            correlation_id=correlation_id,
        )
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32603,
                "message": "Internal error",
            },
        }


async def handle_initialize(message: Dict[str, Any], correlation_id: str):
    """Инициализация MCP-клиента."""
    logger.info("MCP initialization", correlation_id=correlation_id)
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {},
            },
            "serverInfo": {
                "name": settings.app_name,
                "version": settings.app_version,
            },
        },
    }


async def handle_tools_list(message: Dict[str, Any], correlation_id: str):
    """Обработка MCP-запроса tools/list."""
    from app.api.v1 import tools  # локальный импорт, чтобы не ловить циклы

    try:
        tools_map = await tools.tool_registry.get_all_tools()

        tool_items = []
        for tool_name, tool_obj in tools_map.items():
            tool_items.append(
                {
                    "name": tool_obj.name,
                    "description": tool_obj.description,
                    "inputSchema": tool_obj.input_schema,
                }
            )

        logger.info(
            "MCP tools/list handled",
            count=len(tool_items),
            correlation_id=correlation_id,
        )

        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "tools": tool_items,
            },
        }

    except Exception as e:
        logger.error(
            "Failed to handle tools/list",
            error=str(e),
            correlation_id=correlation_id,
        )
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32603,
                "message": "Internal error while listing tools",
            },
        }


async def handle_tools_call(message: Dict[str, Any], correlation_id: str):
    """Обработка MCP-запроса tools/call."""
    from app.api.v1 import tools

    params = message.get("params") or {}
    tool_name = params.get("name")
    arguments = params.get("arguments") or {}
    agent_id = params.get("agent_id") or "mcp-client"

    if not tool_name:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32602,
                "message": "Invalid params: 'name' is required in tools/call",
            },
        }

    try:
        logger.info(
            "MCP tools/call started",
            tool_name=tool_name,
            agent_id=agent_id,
            correlation_id=correlation_id,
        )

        execution = await tools.tool_registry.execute_tool(
            tool_name=tool_name,
            parameters=arguments,
            agent_id=agent_id,
        )

        is_error = execution.error is not None

        content_items = []
        if execution.result is not None:
            content_items.append(
                {
                    "type": "json",
                    "json": execution.result,
                }
            )

        result_payload: Dict[str, Any] = {
            "content": content_items,
            "isError": is_error,
            "toolName": execution.tool_name,
            "executionTime": execution.execution_time,
        }

        if is_error:
            result_payload["error"] = execution.error

        logger.info(
            "MCP tools/call completed",
            tool_name=tool_name,
            agent_id=agent_id,
            is_error=is_error,
            execution_time=execution.execution_time,
            correlation_id=correlation_id,
        )

        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": result_payload,
        }

    except Exception as e:
        logger.error(
            "MCP tools/call failed",
            tool_name=tool_name,
            error=str(e),
            correlation_id=correlation_id,
        )
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32000,
                "message": "Tool execution failed",
                "data": {
                    "toolName": tool_name,
                    "details": str(e),
                },
            },
        }


async def handle_resources_list(message: Dict[str, Any], correlation_id: str):
    """Пока заглушка для resources/list."""
    logger.info("MCP resources/list called", correlation_id=correlation_id)
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {
            "resources": [],
        },
    }


async def handle_resources_read(message: Dict[str, Any], correlation_id: str):
    """Пока заглушка для resources/read."""
    logger.info("MCP resources/read called", correlation_id=correlation_id)
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {
            "contents": [],
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers,
    )
