from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
import structlog

from app.core.models.mcp_protocol import (
    ToolRequest, ToolResponse, MCPTool, ToolExecution
)
from app.core.services.tool_registry import ToolRegistry
from app.core.services.validation_service import ValidationService

logger = structlog.get_logger()
router = APIRouter()
tool_registry = ToolRegistry()
validation_service = ValidationService()


@router.get("/", response_model=Dict[str, MCPTool])
async def list_tools():
    """List all available MCP tools"""
    try:
        tools = await tool_registry.get_all_tools()
        logger.info("Retrieved tools list", count=len(tools))
        return tools
    except Exception as e:
        logger.error("Failed to retrieve tools", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve tools")


@router.get("/{tool_name}", response_model=MCPTool)
async def get_tool(tool_name: str):
    """Get specific tool information"""
    try:
        tool = await tool_registry.get_tool(tool_name)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        return tool
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve tool", tool=tool_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve tool")


@router.post("/execute", response_model=ToolResponse)
async def execute_tool(request: ToolRequest):
    """Execute a tool with given parameters"""
    try:
        # Validate tool exists
        tool = await tool_registry.get_tool(request.tool_name)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' not found")
        
        # Validate parameters
        validation_result = await validation_service.validate_tool_parameters(
            request.tool_name, request.parameters
        )
        if not validation_result.is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid parameters: {validation_result.error_message}"
            )
        
        # Execute tool
        result = await tool_registry.execute_tool(
            request.tool_name, 
            request.parameters,
            request.agent_id
        )
        
        logger.info(
            "Tool executed successfully",
            tool=request.tool_name,
            agent_id=request.agent_id,
            execution_time=result.execution_time
        )
        
        return ToolResponse(
            success=result.error is None,
            result=result.result,
            error=result.error,
            execution_time=result.execution_time or 0.0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to execute tool",
            tool=request.tool_name,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to execute tool")


@router.get("/executions/history", response_model=List[ToolExecution])
async def get_execution_history(limit: int = 50, offset: int = 0):
    """Get tool execution history"""
    try:
        executions = await tool_registry.get_execution_history(limit, offset)
        return executions
    except Exception as e:
        logger.error("Failed to retrieve execution history", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve execution history")


@router.post("/register")
async def register_tool(tool: MCPTool):
    """Register a new tool"""
    try:
        # Validate tool definition
        validation_result = await validation_service.validate_tool_definition(tool)
        if not validation_result.is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tool definition: {validation_result.error_message}"
            )
        
        # Register tool
        await tool_registry.register_tool(tool)
        
        logger.info("Tool registered successfully", tool=tool.name)
        return {"status": "success", "message": f"Tool '{tool.name}' registered successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to register tool", tool=tool.name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to register tool")


@router.delete("/{tool_name}")
async def unregister_tool(tool_name: str):
    """Unregister a tool"""
    try:
        success = await tool_registry.unregister_tool(tool_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        
        logger.info("Tool unregistered successfully", tool=tool_name)
        return {"status": "success", "message": f"Tool '{tool_name}' unregistered successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to unregister tool", tool=tool_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to unregister tool")


@router.get("/categories", response_model=List[str])
async def get_tool_categories():
    """Get all tool categories"""
    try:
        categories = await tool_registry.get_categories()
        return categories
    except Exception as e:
        logger.error("Failed to retrieve tool categories", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve tool categories")


@router.get("/category/{category}", response_model=Dict[str, MCPTool])
async def get_tools_by_category(category: str):
    """Get tools by category"""
    try:
        tools = await tool_registry.get_tools_by_category(category)
        return tools
    except Exception as e:
        logger.error("Failed to retrieve tools by category", category=category, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve tools by category")