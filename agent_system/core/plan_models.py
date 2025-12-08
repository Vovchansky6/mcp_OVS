from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """
    Один шаг плана: какой MCP-tool вызывать и с какими аргументами.
    """
    id: str = Field(..., description="Уникальный ID шага (например, 'step1')")
    tool_name: str = Field(..., alias="tool_name")
    description: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    """
    План, который генерирует Evolution: общая цель + список шагов.
    """
    overall_goal: str
    tool_calls: List[ToolCall] = Field(default_factory=list)


class ToolCallResult(BaseModel):
    """
    Результат выполнения одного шага плана (одного tools/call).
    """
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    success: bool
    result: Any = None
    error: Optional[str] = None


class A2AResponse(BaseModel):
    """
    Итоговый ответ агентской системы в стиле A2A:
    сырые данные + summary + рекомендации + риски.
    """
    query: str
    overall_goal: str
    tool_results: List[ToolCallResult]
    summary: str
    recommendations: List[str]
    risks: List[str]
