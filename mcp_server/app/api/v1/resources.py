from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
import structlog

from app.core.models.mcp_protocol import (
    MCPResource, BusinessTask, TaskRequest, TaskResponse,
    BusinessAnalysisRequest, BusinessAnalysisResponse
)
from app.core.services.resource_manager import ResourceManager
from app.core.services.task_orchestrator import TaskOrchestrator

logger = structlog.get_logger()
router = APIRouter()
resource_manager = ResourceManager()
task_orchestrator = TaskOrchestrator()


@router.get("/", response_model=Dict[str, MCPResource])
async def list_resources():
    """List all available resources"""
    try:
        resources = await resource_manager.get_all_resources()
        logger.info("Retrieved resources list", count=len(resources))
        return resources
    except Exception as e:
        logger.error("Failed to retrieve resources", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve resources")


@router.get("/{resource_uri}")
async def read_resource(resource_uri: str):
    """Read a specific resource"""
    try:
        content = await resource_manager.read_resource(resource_uri)
        if not content:
            raise HTTPException(status_code=404, detail=f"Resource '{resource_uri}' not found")
        
        logger.info("Resource read successfully", uri=resource_uri)
        return {
            "contents": [
                {
                    "uri": resource_uri,
                    "mimeType": "application/json",
                    "text": content
                }
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to read resource", uri=resource_uri, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to read resource")


@router.post("/register")
async def register_resource(resource: MCPResource):
    """Register a new resource"""
    try:
        await resource_manager.register_resource(resource)
        logger.info("Resource registered successfully", uri=resource.uri)
        return {"status": "success", "message": f"Resource '{resource.uri}' registered successfully"}
    except Exception as e:
        logger.error("Failed to register resource", uri=resource.uri, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to register resource")


@router.delete("/{resource_uri}")
async def unregister_resource(resource_uri: str):
    """Unregister a resource"""
    try:
        success = await resource_manager.unregister_resource(resource_uri)
        if not success:
            raise HTTPException(status_code=404, detail=f"Resource '{resource_uri}' not found")
        
        logger.info("Resource unregistered successfully", uri=resource_uri)
        return {"status": "success", "message": f"Resource '{resource_uri}' unregistered successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to unregister resource", uri=resource_uri, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to unregister resource")


@router.post("/tasks", response_model=TaskResponse)
async def create_task(request: TaskRequest):
    """Create a new business task"""
    try:
        task_response = await task_orchestrator.create_task(request)
        logger.info(
            "Task created successfully",
            task_id=task_response.task_id,
            domain=request.domain,
            priority=request.priority
        )
        return task_response
    except Exception as e:
        logger.error("Failed to create task", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create task")


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task details"""
    try:
        task = await task_orchestrator.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve task", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve task")


@router.get("/tasks", response_model=List[BusinessTask])
async def list_tasks(status: str = None, domain: str = None, limit: int = 50, offset: int = 0):
    """List tasks with optional filtering"""
    try:
        tasks = await task_orchestrator.list_tasks(status, domain, limit, offset)
        return tasks
    except Exception as e:
        logger.error("Failed to retrieve tasks", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve tasks")


@router.post("/analysis", response_model=BusinessAnalysisResponse)
async def create_business_analysis(request: BusinessAnalysisRequest):
    """Create a business analysis task"""
    try:
        analysis_response = await task_orchestrator.create_business_analysis(request)
        logger.info(
            "Business analysis created successfully",
            analysis_id=analysis_response.analysis_id,
            domain=request.domain,
            analysis_type=request.analysis_type
        )
        return analysis_response
    except Exception as e:
        logger.error("Failed to create business analysis", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create business analysis")


@router.get("/analysis/{analysis_id}")
async def get_business_analysis(analysis_id: str):
    """Get business analysis results"""
    try:
        analysis = await task_orchestrator.get_business_analysis(analysis_id)
        if not analysis:
            raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve business analysis", analysis_id=analysis_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve business analysis")