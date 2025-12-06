from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
import structlog

from app.core.models.mcp_protocol import Agent, AgentRequest, BusinessTask
from app.core.services.agent_registry import AgentRegistry
from app.core.services.task_orchestrator import TaskOrchestrator

logger = structlog.get_logger()
router = APIRouter()
agent_registry = AgentRegistry()
task_orchestrator = TaskOrchestrator()


@router.get("/agents", response_model=List[Agent])
async def list_agents():
    """List all registered agents"""
    try:
        agents = await agent_registry.get_all_agents()
        logger.info("Retrieved agents list", count=len(agents))
        return agents
    except Exception as e:
        logger.error("Failed to retrieve agents", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve agents")


@router.post("/agents", response_model=Agent)
async def create_agent(request: AgentRequest):
    """Create a new agent"""
    try:
        agent = await agent_registry.create_agent(request)
        logger.info("Agent created successfully", agent_id=agent.id, name=agent.name)
        return agent
    except Exception as e:
        logger.error("Failed to create agent", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create agent")


@router.get("/agents/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str):
    """Get specific agent information"""
    try:
        agent = await agent_registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve agent", agent_id=agent_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve agent")


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete an agent"""
    try:
        success = await agent_registry.delete_agent(agent_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        
        logger.info("Agent deleted successfully", agent_id=agent_id)
        return {"status": "success", "message": f"Agent '{agent_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete agent", agent_id=agent_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete agent")


@router.get("/system/status")
async def get_system_status():
    """Get overall system status"""
    try:
        agents = await agent_registry.get_all_agents()
        tasks = await task_orchestrator.list_tasks()
        
        status = {
            "agents": {
                "total": len(agents),
                "active": len([a for a in agents if a.status == "active"]),
                "idle": len([a for a in agents if a.status == "idle"]),
                "processing": len([a for a in agents if a.status == "processing"]),
                "error": len([a for a in agents if a.status == "error"])
            },
            "tasks": {
                "total": len(tasks),
                "pending": len([t for t in tasks if t.status == "pending"]),
                "processing": len([t for t in tasks if t.status == "processing"]),
                "completed": len([t for t in tasks if t.status == "completed"]),
                "failed": len([t for t in tasks if t.status == "failed"])
            },
            "uptime": 12345,  # This would be calculated
            "version": "1.0.0"
        }
        
        return status
        
    except Exception as e:
        logger.error("Failed to get system status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get system status")


@router.post("/system/shutdown")
async def shutdown_system():
    """Gracefully shutdown the system"""
    try:
        logger.info("System shutdown initiated")
        
        # This would implement graceful shutdown logic
        # - Stop accepting new tasks
        # - Wait for current tasks to complete
        # - Clean up resources
        # - Shutdown agents
        
        return {"status": "success", "message": "System shutdown initiated"}
        
    except Exception as e:
        logger.error("Failed to shutdown system", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to shutdown system")


@router.get("/config")
async def get_system_config():
    """Get system configuration"""
    try:
        # Return non-sensitive configuration
        config = {
            "max_concurrent_agents": 10,
            "agent_timeout": 300,
            "supported_business_domains": ["finance", "healthcare", "retail", "manufacturing", "technology"],
            "default_llm_provider": "evolution",
            "rate_limit_requests": 100,
            "rate_limit_window": 60
        }
        
        return config
        
    except Exception as e:
        logger.error("Failed to get system config", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get system config")