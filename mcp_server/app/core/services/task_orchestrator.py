from typing import Dict, List, Optional, Any
import asyncio
import uuid
import structlog
from datetime import datetime, timedelta

from app.core.models.mcp_protocol import (
    BusinessTask, TaskRequest, TaskResponse, 
    BusinessAnalysisRequest, BusinessAnalysisResponse
)
from app.core.services.agent_registry import AgentRegistry

logger = structlog.get_logger()


class TaskOrchestrator:
    """Orchestrates task execution across agents"""
    
    def __init__(self):
        self.tasks: Dict[str, BusinessTask] = {}
        self.analyses: Dict[str, BusinessAnalysisResponse] = {}
        self.agent_registry = AgentRegistry()
        self._lock = asyncio.Lock()
    
    async def create_task(self, request: TaskRequest) -> TaskResponse:
        """Create and assign a new business task"""
        async with self._lock:
            # Create task
            task = BusinessTask(
                title=request.title,
                description=request.description,
                domain=request.domain,
                priority=request.priority,
                input_data=request.input_data
            )
            
            # Store task
            self.tasks[task.id] = task
            
            # Find suitable agent
            agent_id = await self._find_suitable_agent(task)
            
            if agent_id:
                # Assign task to agent
                agent = await self.agent_registry.get_agent(agent_id)
                if agent:
                    await self._assign_task_to_agent(task, agent_id)
                    task.agent_id = agent_id
                    task.status = "processing"
                    task.started_at = datetime.utcnow()
                    
                    logger.info(
                        "Task assigned to agent",
                        task_id=task.id,
                        agent_id=agent_id
                    )
                    
                    return TaskResponse(
                        task_id=task.id,
                        status="processing",
                        agent_id=agent_id,
                        estimated_completion_time=datetime.utcnow() + timedelta(minutes=30)
                    )
            
            # No suitable agent found, keep as pending
            logger.warning(
                "No suitable agent found for task",
                task_id=task.id,
                domain=request.domain
            )
            
            return TaskResponse(
                task_id=task.id,
                status="pending",
                agent_id=None
            )
    
    async def get_task(self, task_id: str) -> Optional[BusinessTask]:
        """Get task by ID"""
        async with self._lock:
            return self.tasks.get(task_id)
    
    async def list_tasks(
        self, 
        status: str = None, 
        domain: str = None, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[BusinessTask]:
        """List tasks with optional filtering"""
        async with self._lock:
            tasks = list(self.tasks.values())
            
            # Apply filters
            if status:
                tasks = [t for t in tasks if t.status == status]
            
            if domain:
                tasks = [t for t in tasks if t.domain == domain]
            
            # Sort by creation time (newest first)
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            
            # Apply pagination
            return tasks[offset:offset + limit]
    
    async def create_business_analysis(
        self, 
        request: BusinessAnalysisRequest
    ) -> BusinessAnalysisResponse:
        """Create a business analysis task"""
        async with self._lock:
            analysis_id = str(uuid.uuid4())
            
            # Create analysis response
            analysis = BusinessAnalysisResponse(
                analysis_id=analysis_id,
                status="processing"
            )
            
            # Store analysis
            self.analyses[analysis_id] = analysis
            
            # Create sub-tasks for analysis
            await self._create_analysis_subtasks(request, analysis_id)
            
            logger.info(
                "Business analysis created",
                analysis_id=analysis_id,
                domain=request.domain,
                analysis_type=request.analysis_type
            )
            
            return analysis
    
    async def get_business_analysis(self, analysis_id: str) -> Optional[BusinessAnalysisResponse]:
        """Get business analysis by ID"""
        async with self._lock:
            return self.analyses.get(analysis_id)
    
    async def update_task_status(
        self, 
        task_id: str, 
        status: str, 
        result: Dict[str, Any] = None,
        error: str = None
    ):
        """Update task status"""
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                logger.warning("Task not found for status update", task_id=task_id)
                return
            
            task.status = status
            
            if status == "completed":
                task.completed_at = datetime.utcnow()
                if result:
                    task.output_data = result
                
                logger.info("Task completed", task_id=task_id)
                
            elif status == "failed":
                task.completed_at = datetime.utcnow()
                task.error_message = error
                
                logger.error("Task failed", task_id=task_id, error=error)
    
    async def _find_suitable_agent(self, task: BusinessTask) -> Optional[str]:
        """Find a suitable agent for the task"""
        # Determine required capabilities based on task domain
        required_capabilities = self._get_required_capabilities(task)
        
        # Find agents with required capabilities
        capable_agents = await self.agent_registry.find_capable_agents(
            required_capabilities
        )
        
        if not capable_agents:
            return None
        
        # Select agent (simple round-robin for now)
        # In a real implementation, this would consider agent load, specialization, etc.
        return capable_agents[0]
    
    def _get_required_capabilities(self, task: BusinessTask) -> List[str]:
        """Determine required capabilities for a task"""
        capabilities = []
        
        # Domain-specific capabilities
        if task.domain == "finance":
            capabilities.extend(["financial_analysis", "data_processing"])
        elif task.domain == "healthcare":
            capabilities.extend(["data_validation", "compliance_check"])
        elif task.domain == "retail":
            capabilities.extend(["sales_analysis", "inventory_management"])
        elif task.domain == "manufacturing":
            capabilities.extend(["production_analysis", "quality_control"])
        elif task.domain == "technology":
            capabilities.extend(["system_monitoring", "performance_analysis"])
        
        # General capabilities
        capabilities.extend(["report_generation", "data_visualization"])
        
        return capabilities
    
    async def _assign_task_to_agent(self, task: BusinessTask, agent_id: str):
        """Assign task to a specific agent"""
        # This would use the agent registry to assign the task
        # For now, we'll just log the assignment
        logger.info(
            "Assigning task to agent",
            task_id=task.id,
            agent_id=agent_id
        )
        
        # In a real implementation:
        # agent = await self.agent_registry.get_agent(agent_id)
        # await agent.assign_task(task)
    
    async def _create_analysis_subtasks(
        self, 
        request: BusinessAnalysisRequest, 
        analysis_id: str
    ):
        """Create sub-tasks for business analysis"""
        subtasks = []
        
        # Data collection task
        data_collection_task = TaskRequest(
            title=f"Data Collection for {analysis_id}",
            description=f"Collect data from sources: {', '.join(request.data_sources)}",
            domain=request.domain,
            priority="high",
            input_data={
                "data_sources": request.data_sources,
                "analysis_id": analysis_id
            }
        )
        
        # Analysis task
        analysis_task = TaskRequest(
            title=f"Analysis Execution for {analysis_id}",
            description=f"Execute {request.analysis_type} analysis",
            domain=request.domain,
            priority="high",
            input_data={
                "analysis_type": request.analysis_type,
                "parameters": request.parameters,
                "analysis_id": analysis_id
            }
        )
        
        # Report generation task
        report_task = TaskRequest(
            title=f"Report Generation for {analysis_id}",
            description="Generate analysis report",
            domain=request.domain,
            priority="medium",
            input_data={
                "analysis_id": analysis_id,
                "include_visualizations": True
            }
        )
        
        # Create tasks
        for task_request in [data_collection_task, analysis_task, report_task]:
            await self.create_task(task_request)
            subtasks.append(task_request.title)
        
        logger.info(
            "Analysis sub-tasks created",
            analysis_id=analysis_id,
            subtask_count=len(subtasks),
            subtasks=subtasks
        )
    
    async def get_task_statistics(self) -> Dict[str, Any]:
        """Get task statistics"""
        async with self._lock:
            total_tasks = len(self.tasks)
            completed_tasks = len([t for t in self.tasks.values() if t.status == "completed"])
            failed_tasks = len([t for t in self.tasks.values() if t.status == "failed"])
            processing_tasks = len([t for t in self.tasks.values() if t.status == "processing"])
            pending_tasks = len([t for t in self.tasks.values() if t.status == "pending"])
            
            return {
                "total": total_tasks,
                "completed": completed_tasks,
                "failed": failed_tasks,
                "processing": processing_tasks,
                "pending": pending_tasks,
                "success_rate": completed_tasks / total_tasks if total_tasks > 0 else 0
            }