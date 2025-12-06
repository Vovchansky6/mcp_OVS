from fastapi import Request
import time
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

logger = structlog.get_logger()

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

TOOL_EXECUTIONS = Counter(
    'tool_executions_total',
    'Total tool executions',
    ['tool_name', 'status']
)

TOOL_EXECUTION_DURATION = Histogram(
    'tool_execution_duration_seconds',
    'Tool execution duration in seconds',
    ['tool_name']
)

AGENT_TASKS = Counter(
    'agent_tasks_total',
    'Total agent tasks',
    ['agent_id', 'status']
)

LLM_TOKENS_USED = Counter(
    'llm_tokens_used_total',
    'Total LLM tokens used',
    ['provider', 'model']
)


class MetricsMiddleware:
    """Middleware to collect Prometheus metrics"""
    
    async def __call__(self, request: Request, call_next):
        start_time = time.time()
        
        # Increment active connections
        ACTIVE_CONNECTIONS.inc()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
            
            # Log if slow request
            if duration > 1.0:
                logger.warning(
                    "Slow request detected",
                    method=request.method,
                    path=request.url.path,
                    duration=duration,
                    correlation_id=getattr(request.state, "correlation_id", None)
                )
            
            return response
            
        except Exception as e:
            # Record error metrics
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=500
            ).inc()
            
            logger.error(
                "Request failed with exception",
                method=request.method,
                path=request.url.path,
                error=str(e),
                correlation_id=getattr(request.state, "correlation_id", None)
            )
            
            raise
            
        finally:
            # Decrement active connections
            ACTIVE_CONNECTIONS.dec()


def get_metrics():
    """Get Prometheus metrics as HTTP response"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


def record_tool_execution(tool_name: str, success: bool, duration: float):
    """Record tool execution metrics"""
    TOOL_EXECUTIONS.labels(
        tool_name=tool_name,
        status='success' if success else 'error'
    ).inc()
    
    TOOL_EXECUTION_DURATION.labels(tool_name=tool_name).observe(duration)


def record_agent_task(agent_id: str, status: str):
    """Record agent task metrics"""
    AGENT_TASKS.labels(agent_id=agent_id, status=status).inc()


def record_llm_tokens(provider: str, model: str, tokens: int):
    """Record LLM token usage"""
    LLM_TOKENS_USED.labels(provider=provider, model=model).inc(tokens)