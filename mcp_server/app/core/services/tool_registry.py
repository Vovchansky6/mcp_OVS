from typing import Dict, List, Optional, Any
import asyncio
import time
import uuid
from datetime import datetime

import httpx
import structlog

from app.config import settings
from app.core.models.mcp_protocol import MCPTool, ToolExecution, ToolStatus
from app.exceptions import ToolExecutionException, ValidationException

logger = structlog.get_logger()


class ToolRegistry:
    """Registry for managing MCP tools and delegating execution to go-biz-engine."""

    def __init__(self) -> None:
        self.tools: Dict[str, MCPTool] = {}
        self.executions: List[ToolExecution] = []
        self._lock = asyncio.Lock()

    # -------------------------------------------------------------------------
    # Tool metadata management
    # -------------------------------------------------------------------------

    async def register_tool(self, tool: MCPTool) -> None:
        """Register or update a tool in the registry."""
        async with self._lock:
            self.tools[tool.name] = tool
            logger.info("Tool registered", tool_name=tool.name, category=tool.category)

    async def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """Get a single tool by name."""
        async with self._lock:
            return self.tools.get(tool_name)

    async def get_all_tools(self) -> Dict[str, MCPTool]:
        """Return all registered tools as a dict[name, MCPTool]."""
        async with self._lock:
            return dict(self.tools)

    async def get_tools_by_category(self, category: str) -> Dict[str, MCPTool]:
        """Return tools filtered by category."""
        async with self._lock:
            return {
                name: tool
                for name, tool in self.tools.items()
                if tool.category == category
            }

    async def get_categories(self) -> List[str]:
        """Return a list of unique tool categories."""
        async with self._lock:
            categories = {tool.category for tool in self.tools.values() if tool.category}
        return sorted(categories)

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        agent_id: Optional[str] = None,
    ) -> ToolExecution:
        """Execute a tool by delegating to the external go-biz-engine service."""

        execution = ToolExecution(
            tool_name=tool_name,
            agent_id=agent_id or "system",
            parameters=parameters or {},
        )

        start_time = time.time()
        correlation_id = str(uuid.uuid4())

        try:
            # Check tool registration & status
            async with self._lock:
                tool = self.tools.get(tool_name)

            if not tool:
                raise ToolExecutionException(tool_name, "Tool is not registered in registry")

            if tool.status != ToolStatus.ACTIVE:
                raise ToolExecutionException(
                    tool_name,
                    f"Tool status is {tool.status}, expected ACTIVE",
                )

            # Basic parameter validation: ensure dict
            if not isinstance(parameters, dict):
                raise ValidationException(
                    message="Tool parameters must be an object (JSON dict)",
                    field="parameters",
                )

            # Build payload for go-biz-engine
            payload: Dict[str, Any] = {
                "tool_name": tool_name,
                "params": parameters,
                "correlation_id": correlation_id,
                "user_id": execution.agent_id,
                "request_ts": datetime.utcnow().isoformat() + "Z",
                "context": {
                    "source": "mcp-biz-server",
                    "agent_id": execution.agent_id,
                },
            }

            base_url = settings.go_biz_engine_url.rstrip("/")
            url = f"{base_url}/execute-tool"

            logger.info(
                "Calling go-biz-engine",
                tool_name=tool_name,
                agent_id=execution.agent_id,
                url=url,
                correlation_id=correlation_id,
            )

            # HTTP call to Go service
            try:
                async with httpx.AsyncClient(
                    timeout=settings.go_biz_engine_timeout
                ) as client:
                    response = await client.post(url, json=payload)
            except httpx.RequestError as e:
                raise ToolExecutionException(
                    tool_name,
                    f"Failed to call go-biz-engine: {str(e)}",
                ) from e

            if response.status_code != 200:
                text_preview = response.text[:200] if response.text else ""
                raise ToolExecutionException(
                    tool_name,
                    f"go-biz-engine returned HTTP {response.status_code}: {text_preview}",
                )

            # Parse JSON body
            try:
                body = response.json()
            except ValueError as e:
                raise ToolExecutionException(
                    tool_name,
                    f"Invalid JSON from go-biz-engine: {str(e)}",
                ) from e

            status = body.get("status")
            data = body.get("data")
            error_obj = body.get("error") or {}

            execution.execution_time = time.time() - start_time

            if status == "success":
                execution.result = data
                execution.error = None

                logger.info(
                    "Tool executed successfully via go-biz-engine",
                    tool_name=tool_name,
                    agent_id=execution.agent_id,
                    execution_time=execution.execution_time,
                    correlation_id=correlation_id,
                )
            else:
                message = error_obj.get("message") or f"go-biz-engine returned status '{status}'"
                execution.result = data
                execution.error = message

                logger.warning(
                    "Tool executed with error via go-biz-engine",
                    tool_name=tool_name,
                    agent_id=execution.agent_id,
                    error=message,
                    correlation_id=correlation_id,
                )

        except Exception as e:
            if execution.execution_time is None:
                execution.execution_time = time.time() - start_time
            if execution.error is None:
                execution.error = str(e)

            logger.error(
                "Tool execution failed",
                tool_name=tool_name,
                agent_id=agent_id,
                error=str(e),
                execution_time=execution.execution_time,
            )

            # Re-raise non-ToolExecutionException for FastAPI (internal errors)
            if not isinstance(e, ToolExecutionException):
                raise

        finally:
            # Store execution history
            async with self._lock:
                self.executions.append(execution)
                if len(self.executions) > 1000:
                    self.executions = self.executions[-1000:]

        return execution

    async def get_execution_history(self, limit: int = 50, offset: int = 0) -> List[ToolExecution]:
        """Get tool execution history."""
        async with self._lock:
            return self.executions[offset: offset + limit]
