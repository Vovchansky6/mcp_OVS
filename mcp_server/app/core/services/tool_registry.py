from typing import Dict, List, Optional, Any
import asyncio
import time
import uuid
import structlog
from datetime import datetime

from app.core.models.mcp_protocol import MCPTool, ToolExecution, ToolStatus
from app.exceptions import ToolExecutionException, ValidationException

logger = structlog.get_logger()


class ToolRegistry:
    """Registry for managing MCP tools"""
    
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self.executions: List[ToolExecution] = []
        self._lock = asyncio.Lock()
    
    async def register_tool(self, tool: MCPTool) -> bool:
        """Register a new tool"""
        async with self._lock:
            if tool.name in self.tools:
                logger.warning("Tool already exists, overwriting", tool_name=tool.name)
            
            self.tools[tool.name] = tool
            logger.info("Tool registered successfully", tool_name=tool.name)
            return True
    
    async def unregister_tool(self, tool_name: str) -> bool:
        """Unregister a tool"""
        async with self._lock:
            if tool_name not in self.tools:
                return False
            
            del self.tools[tool_name]
            logger.info("Tool unregistered successfully", tool_name=tool_name)
            return True
    
    async def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """Get a specific tool"""
        async with self._lock:
            return self.tools.get(tool_name)
    
    async def get_all_tools(self) -> Dict[str, MCPTool]:
        """Get all registered tools"""
        async with self._lock:
            return self.tools.copy()
    
    async def get_tools_by_category(self, category: str) -> Dict[str, MCPTool]:
        """Get tools by category"""
        async with self._lock:
            return {
                name: tool for name, tool in self.tools.items()
                if tool.category == category
            }
    
    async def get_categories(self) -> List[str]:
        """Get all tool categories"""
        async with self._lock:
            categories = set()
            for tool in self.tools.values():
                if tool.category:
                    categories.add(tool.category)
            return list(categories)
    
    async def execute_tool(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any],
        agent_id: Optional[str] = None
    ) -> ToolExecution:
        """Execute a tool"""
        execution = ToolExecution(
            tool_name=tool_name,
            agent_id=agent_id or "system",
            parameters=parameters
        )
        
        start_time = time.time()
        
        try:
            # Get tool
            tool = await self.get_tool(tool_name)
            if not tool:
                raise ToolExecutionException(tool_name, "Tool not found")
            
            if tool.status != ToolStatus.ACTIVE:
                raise ToolExecutionException(tool_name, f"Tool is {tool.status}")
            
            # Execute tool (this would call the actual tool implementation)
            result = await self._execute_tool_implementation(tool, parameters)
            
            execution.result = result
            execution.execution_time = time.time() - start_time
            
            logger.info(
                "Tool executed successfully",
                tool_name=tool_name,
                agent_id=agent_id,
                execution_time=execution.execution_time
            )
            
        except Exception as e:
            execution.error = str(e)
            execution.execution_time = time.time() - start_time
            
            logger.error(
                "Tool execution failed",
                tool_name=tool_name,
                agent_id=agent_id,
                error=str(e),
                execution_time=execution.execution_time
            )
            
            if not isinstance(e, ToolExecutionException):
                raise ToolExecutionException(tool_name, str(e))
            
            raise
        
        finally:
            # Store execution history
            async with self._lock:
                self.executions.append(execution)
                # Keep only last 1000 executions
                if len(self.executions) > 1000:
                    self.executions = self.executions[-1000:]
        
        return execution
    
    async def _execute_tool_implementation(self, tool: MCPTool, parameters: Dict[str, Any]) -> Any:
        """Execute the actual tool implementation"""
        # This is where you would implement the actual tool logic
        # For now, we'll simulate different tool types
        
        if tool.name == "financial_analyzer":
            return await self._execute_financial_analyzer(parameters)
        elif tool.name == "api_connector":
            return await self._execute_api_connector(parameters)
        elif tool.name == "data_validator":
            return await self._execute_data_validator(parameters)
        elif tool.name == "report_generator":
            return await self._execute_report_generator(parameters)
        elif tool.name == "database_query":
            return await self._execute_database_query(parameters)
        elif tool.name == "llm_processor":
            return await self._execute_llm_processor(parameters)
        else:
            # Generic tool execution
            await asyncio.sleep(0.1)  # Simulate processing time
            return {
                "status": "success",
                "message": f"Tool '{tool.name}' executed successfully",
                "parameters": parameters,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _execute_financial_analyzer(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate financial analysis tool"""
        await asyncio.sleep(0.5)  # Simulate processing
        
        return {
            "analysis": {
                "revenue_growth": 15.3,
                "profit_margin": 12.7,
                "cost_reduction": 8.2,
                "roi": 23.5
            },
            "insights": [
                "Revenue growth exceeds industry average",
                "Cost reduction opportunities identified",
                "ROI shows positive trend"
            ],
            "recommendations": [
                "Focus on high-margin product lines",
                "Optimize supply chain costs",
                "Invest in growth markets"
            ]
        }
    
    async def _execute_api_connector(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate API connector tool"""
        await asyncio.sleep(0.3)  # Simulate API call
        
        return {
            "status": "success",
            "data": {
                "records_processed": len(parameters.get("data", [])),
                "api_response": {"status": "ok", "message": "Data processed successfully"}
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _execute_data_validator(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate data validation tool"""
        await asyncio.sleep(0.2)  # Simulate validation
        
        return {
            "validation": {
                "is_valid": True,
                "errors": [],
                "warnings": ["Optional field missing"]
            },
            "statistics": {
                "fields_validated": 10,
                "records_checked": 1
            }
        }
    
    async def _execute_report_generator(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate report generator tool"""
        await asyncio.sleep(1.0)  # Simulate report generation
        
        return {
            "report": {
                "id": str(uuid.uuid4()),
                "type": parameters.get("report_type", "summary"),
                "format": "pdf",
                "size_kb": 245,
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _execute_database_query(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate database query tool"""
        await asyncio.sleep(0.4)  # Simulate query
        
        return {
            "query_result": {
                "rows_returned": 42,
                "execution_time_ms": 150,
                "data": [{"id": 1, "name": "Sample Data"}]  # Sample data
            }
        }
    
    async def _execute_llm_processor(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate LLM processing tool"""
        await asyncio.sleep(0.8)  # Simulate LLM call
        
        return {
            "llm_response": {
                "content": f"Processed: {parameters.get('prompt', 'No prompt')}",
                "tokens_used": 156,
                "model": "evolution-llm-v1",
                "confidence": 0.92
            }
        }
    
    async def get_execution_history(self, limit: int = 50, offset: int = 0) -> List[ToolExecution]:
        """Get tool execution history"""
        async with self._lock:
            return self.executions[offset:offset + limit]