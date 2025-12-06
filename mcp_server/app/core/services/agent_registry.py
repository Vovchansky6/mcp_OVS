from typing import Dict, List, Optional, Type
import asyncio
import structlog
from datetime import datetime

from app.core.models.mcp_protocol import Agent, AgentRequest, AgentStatus
from agent_system.core.base_agent import BaseAgent

logger = structlog.get_logger()


class AgentRegistry:
    """Registry for managing agents"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_types: Dict[str, Type[BaseAgent]] = {}
        self._lock = asyncio.Lock()
    
    def register_agent_type(self, agent_type: str, agent_class: Type[BaseAgent]):
        """Register a new agent type"""
        self.agent_types[agent_type] = agent_class
        logger.info("Agent type registered", agent_type=agent_type)
    
    async def create_agent(self, request: AgentRequest) -> Agent:
        """Create a new agent"""
        async with self._lock:
            # Check if agent type is registered
            if request.type not in self.agent_types:
                raise Exception(f"Unknown agent type: {request.type}")
            
            # Create agent instance
            agent_class = self.agent_types[request.type]
            agent = agent_class(
                agent_id="",  # Will be generated
                name=request.name,
                agent_type=request.type,
                capabilities=request.capabilities,
                config=request.config
            )
            
            # Store agent
            self.agents[agent.id] = agent
            
            # Start agent
            await agent.start()
            
            logger.info(
                "Agent created and started",
                agent_id=agent.id,
                name=request.name,
                type=request.type
            )
            
            # Return agent model
            return Agent(
                id=agent.id,
                name=agent.name,
                type=agent.type,
                description=request.description,
                capabilities=agent.capabilities,
                status=agent.status,
                tasks_completed=agent.tasks_completed,
                last_activity=agent.last_activity,
                config=agent.config
            )
    
    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID"""
        async with self._lock:
            agent = self.agents.get(agent_id)
            if not agent:
                return None
            
            return Agent(
                id=agent.id,
                name=agent.name,
                type=agent.type,
                description="",  # Would be stored separately
                capabilities=agent.capabilities,
                status=agent.status,
                current_task_id=agent.current_task.id if agent.current_task else None,
                tasks_completed=agent.tasks_completed,
                last_activity=agent.last_activity,
                config=agent.config
            )
    
    async def get_all_agents(self) -> List[Agent]:
        """Get all agents"""
        async with self._lock:
            agents = []
            for agent in self.agents.values():
                agents.append(Agent(
                    id=agent.id,
                    name=agent.name,
                    type=agent.type,
                    description="",  # Would be stored separately
                    capabilities=agent.capabilities,
                    status=agent.status,
                    current_task_id=agent.current_task.id if agent.current_task else None,
                    tasks_completed=agent.tasks_completed,
                    last_activity=agent.last_activity,
                    config=agent.config
                ))
            return agents
    
    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent"""
        async with self._lock:
            agent = self.agents.get(agent_id)
            if not agent:
                return False
            
            # Stop agent
            await agent.stop()
            
            # Remove from registry
            del self.agents[agent_id]
            
            logger.info("Agent deleted", agent_id=agent_id)
            return True
    
    async def find_capable_agents(self, capabilities: List[str]) -> List[str]:
        """Find agents that have the required capabilities"""
        async with self._lock:
            capable_agents = []
            for agent_id, agent in self.agents.items():
                if agent.status == AgentStatus.IDLE:
                    # Check if agent has all required capabilities
                    if all(cap in agent.capabilities for cap in capabilities):
                        capable_agents.append(agent_id)
            
            return capable_agents
    
    async def get_idle_agents(self) -> List[str]:
        """Get all idle agents"""
        async with self._lock:
            return [
                agent_id for agent_id, agent in self.agents.items()
                if agent.status == AgentStatus.IDLE
            ]
    
    async def get_agent_statistics(self) -> Dict[str, int]:
        """Get agent statistics"""
        async with self._lock:
            stats = {
                "total": len(self.agents),
                "idle": 0,
                "active": 0,
                "processing": 0,
                "error": 0
            }
            
            for agent in self.agents.values():
                stats[agent.status.value] += 1
            
            return stats
    
    async def shutdown_all_agents(self):
        """Shutdown all agents"""
        async with self._lock:
            logger.info("Shutting down all agents", count=len(self.agents))
            
            # Stop all agents
            tasks = [agent.stop() for agent in self.agents.values()]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Clear registry
            self.agents.clear()
            
            logger.info("All agents shut down")