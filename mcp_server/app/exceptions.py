from typing import Optional, Dict, Any


class MCPException(Exception):
    """Base MCP exception"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "MCP_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(MCPException):
    """Validation error exception"""
    
    def __init__(self, message: str, field: str = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details={"field": field} if field else None
        )
        self.field = field


class AuthenticationException(MCPException):
    """Authentication error exception"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401
        )


class AuthorizationException(MCPException):
    """Authorization error exception"""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403
        )


class ResourceNotFoundException(MCPException):
    """Resource not found exception"""
    
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} '{resource_id}' not found",
            error_code="RESOURCE_NOT_FOUND",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id}
        )


class ToolExecutionException(MCPException):
    """Tool execution error exception"""
    
    def __init__(self, tool_name: str, error_message: str):
        super().__init__(
            message=f"Tool '{tool_name}' execution failed: {error_message}",
            error_code="TOOL_EXECUTION_ERROR",
            status_code=500,
            details={"tool_name": tool_name, "error": error_message}
        )


class AgentException(MCPException):
    """Agent-related exception"""
    
    def __init__(self, agent_id: str, message: str):
        super().__init__(
            message=f"Agent '{agent_id}': {message}",
            error_code="AGENT_ERROR",
            status_code=500,
            details={"agent_id": agent_id}
        )


class ExternalAPIException(MCPException):
    """External API error exception"""
    
    def __init__(self, api_name: str, status_code: int, error_message: str):
        super().__init__(
            message=f"External API '{api_name}' error: {error_message}",
            error_code="EXTERNAL_API_ERROR",
            status_code=502,
            details={
                "api_name": api_name,
                "api_status_code": status_code,
                "error": error_message
            }
        )


class LLMException(MCPException):
    """LLM provider error exception"""
    
    def __init__(self, provider: str, model: str, error_message: str):
        super().__init__(
            message=f"LLM provider '{provider}' model '{model}' error: {error_message}",
            error_code="LLM_ERROR",
            status_code=500,
            details={"provider": provider, "model": model, "error": error_message}
        )


class CircuitBreakerException(MCPException):
    """Circuit breaker exception"""
    
    def __init__(self, service_name: str):
        super().__init__(
            message=f"Service '{service_name}' circuit breaker is open",
            error_code="CIRCUIT_BREAKER_OPEN",
            status_code=503,
            details={"service_name": service_name}
        )


class RateLimitException(Exception):
    """Rate limit exceeded exception"""
    
    def __init__(self, limit: int, window: int, retry_after: int):
        self.limit = limit
        self.window = window
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded: {limit} requests per {window} seconds")


class ConfigurationException(MCPException):
    """Configuration error exception"""
    
    def __init__(self, config_key: str, message: str):
        super().__init__(
            message=f"Configuration error for '{config_key}': {message}",
            error_code="CONFIGURATION_ERROR",
            status_code=500,
            details={"config_key": config_key}
        )