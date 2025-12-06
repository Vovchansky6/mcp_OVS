from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from datetime import datetime
import uuid


class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"


class ToolStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class AgentStatus(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    PROCESSING = "processing"
    ERROR = "error"


# MCP Protocol Models
class MCPMessage(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class MCPTool(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    status: ToolStatus = ToolStatus.ACTIVE
    category: Optional[str] = None
    tags: List[str] = []


class MCPResource(BaseModel):
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


class MCPCapability(BaseModel):
    tools: Optional[Dict[str, MCPTool]] = None
    resources: Optional[Dict[str, MCPResource]] = None
    prompts: Optional[Dict[str, Any]] = None


# Business Domain Models
class BusinessTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    domain: str
    priority: str = "medium"
    status: str = "pending"
    agent_id: Optional[str] = None
    input_data: Dict[str, Any] = {}
    output_data: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class Agent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: str
    description: str
    capabilities: List[str]
    status: AgentStatus = AgentStatus.IDLE
    current_task_id: Optional[str] = None
    tasks_completed: int = 0
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    config: Dict[str, Any] = {}


class ToolExecution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    agent_id: str
    task_id: Optional[str] = None
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExternalAPIConfig(BaseModel):
    name: str
    base_url: str
    api_key: Optional[str] = None
    timeout: int = 30
    retry_attempts: int = 3
    rate_limit_per_minute: int = 60


class BusinessRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    domain: str
    condition: str
    action: str
    priority: int = 1
    active: bool = True


class MonitoringMetrics(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    active_agents: int
    processing_tasks: int
    completed_tasks: int
    failed_tasks: int
    average_response_time: float
    requests_per_second: float
    error_rate: float


class HealthStatus(BaseModel):
    status: str  # healthy, degraded, unhealthy
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, bool]
    uptime_seconds: int
    version: str


# API Request/Response Models
class ToolRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]
    agent_id: Optional[str] = None


class ToolResponse(BaseModel):
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float


class AgentRequest(BaseModel):
    name: str
    type: str
    description: str
    capabilities: List[str]
    config: Dict[str, Any] = {}


class TaskRequest(BaseModel):
    title: str
    description: str
    domain: str
    priority: str = "medium"
    input_data: Dict[str, Any] = {}
    preferred_agent_id: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    status: str
    agent_id: Optional[str] = None
    estimated_completion_time: Optional[datetime] = None


class BusinessAnalysisRequest(BaseModel):
    domain: str
    data_sources: List[str]
    analysis_type: str
    parameters: Dict[str, Any] = {}


class BusinessAnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    results: Optional[Dict[str, Any]] = None
    insights: List[str] = []
    recommendations: List[str] = []
    confidence_score: Optional[float] = None