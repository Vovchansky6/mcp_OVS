#!/usr/bin/env python3
"""
MCP Business AI Transformation - Agent System Entry Point

This module initializes and runs the multi-agent system for business AI transformation.
It manages agent lifecycle, task distribution, and inter-agent communication.
"""

import asyncio
import signal
import sys
import os
from typing import Dict, List, Optional
import structlog
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_system.core.base_agent import BaseAgent, MessageType, AgentMessage
from agent_system.agents.specialists.api_executor import APIExecutorAgent
from agent_system.agents.specialists.data_analyst import DataAnalystAgent
from agent_system.llm.providers.evolution_provider import EvolutionProvider
from agent_system.llm.providers.openai_provider import OpenAIProvider

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class AgentSystemConfig:
    """Configuration for the Agent System"""
    
    def __init__(self):
        self.mcp_server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.evolution_api_key = os.getenv("EVOLUTION_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.max_agents = int(os.getenv("MAX_AGENTS", "10"))
        self.heartbeat_interval = int(os.getenv("HEARTBEAT_INTERVAL", "30"))
        self.task_timeout = int(os.getenv("TASK_TIMEOUT", "300"))


class AgentSystem:
    """
    Main Agent System orchestrator.
    
    Manages the lifecycle of all agents, handles task distribution,
    and coordinates inter-agent communication.
    """
    
    def __init__(self, config: AgentSystemConfig):
        self.config = config
        self.agents: Dict[str, BaseAgent] = {}
        self.running = False
        self._shutdown_event = asyncio.Event()
        self._tasks: List[asyncio.Task] = []
        
        # Initialize LLM providers
        self.llm_providers = {}
        self._init_llm_providers()
        
        logger.info(
            "Agent System initialized",
            mcp_server_url=config.mcp_server_url,
            max_agents=config.max_agents
        )
    
    def _init_llm_providers(self):
        """Initialize LLM providers based on available API keys"""
        if self.config.evolution_api_key:
            self.llm_providers["evolution"] = EvolutionProvider({
                "api_key": self.config.evolution_api_key
            })
            logger.info("Evolution LLM provider initialized")
        
        if self.config.openai_api_key:
            self.llm_providers["openai"] = OpenAIProvider({
                "api_key": self.config.openai_api_key
            })
            logger.info("OpenAI LLM provider initialized")
        
        if not self.llm_providers:
            logger.warning("No LLM providers configured. Set EVOLUTION_API_KEY or OPENAI_API_KEY")
    
    async def start(self):
        """Start the Agent System"""
        if self.running:
            logger.warning("Agent System already running")
            return
        
        self.running = True
        logger.info("Starting Agent System")
        
        try:
            # Initialize default agents
            await self._init_default_agents()
            
            # Start all agents
            for agent_id, agent in self.agents.items():
                await agent.start()
                logger.info("Agent started", agent_id=agent_id, agent_name=agent.name)
            
            # Start background tasks
            self._tasks.append(asyncio.create_task(self._heartbeat_loop()))
            self._tasks.append(asyncio.create_task(self._task_polling_loop()))
            self._tasks.append(asyncio.create_task(self._mcp_server_sync_loop()))
            
            logger.info(
                "Agent System started successfully",
                active_agents=len(self.agents),
                llm_providers=list(self.llm_providers.keys())
            )
            
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
        except Exception as e:
            logger.error("Error starting Agent System", error=str(e))
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the Agent System"""
        if not self.running:
            return
        
        logger.info("Stopping Agent System")
        self.running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Stop all agents
        for agent_id, agent in self.agents.items():
            await agent.stop()
            logger.info("Agent stopped", agent_id=agent_id)
        
        self.agents.clear()
        logger.info("Agent System stopped")
    
    async def _init_default_agents(self):
        """Initialize default specialist agents"""
        
        # API Executor Agent
        api_executor = APIExecutorAgent(
            agent_id="api-executor-001",
            config={
                "api_configs": {},
                "max_concurrent_calls": 5
            }
        )
        self.agents[api_executor.id] = api_executor
        
        # Data Analyst Agent
        data_analyst = DataAnalystAgent(
            agent_id="data-analyst-001",
            config={
                "llm_provider": self.llm_providers.get("evolution") or self.llm_providers.get("openai"),
                "analysis_types": ["financial", "trend", "comparative"]
            }
        )
        self.agents[data_analyst.id] = data_analyst
        
        logger.info(
            "Default agents initialized",
            agent_count=len(self.agents),
            agents=list(self.agents.keys())
        )
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats for all agents"""
        while self.running:
            try:
                for agent_id, agent in self.agents.items():
                    status = agent.get_status()
                    logger.debug(
                        "Agent heartbeat",
                        agent_id=agent_id,
                        status=status["status"],
                        tasks_completed=status["tasks_completed"]
                    )
                
                await asyncio.sleep(self.config.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in heartbeat loop", error=str(e))
                await asyncio.sleep(5)
    
    async def _task_polling_loop(self):
        """Poll MCP server for new tasks"""
        import httpx
        
        while self.running:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    # Poll for pending tasks
                    response = await client.get(
                        f"{self.config.mcp_server_url}/api/v1/resources/tasks",
                        params={"status": "pending", "limit": 10}
                    )
                    
                    if response.status_code == 200:
                        tasks = response.json()
                        for task in tasks:
                            await self._assign_task(task)
                    
                await asyncio.sleep(5)  # Poll every 5 seconds
                
            except asyncio.CancelledError:
                break
            except httpx.ConnectError:
                logger.debug("MCP server not available, retrying...")
                await asyncio.sleep(10)
            except Exception as e:
                logger.error("Error in task polling loop", error=str(e))
                await asyncio.sleep(5)
    
    async def _mcp_server_sync_loop(self):
        """Sync agent status with MCP server"""
        import httpx
        
        while self.running:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    # Register/update agents on MCP server
                    for agent_id, agent in self.agents.items():
                        status = agent.get_status()
                        
                        await client.post(
                            f"{self.config.mcp_server_url}/api/v1/admin/agents/status",
                            json={
                                "agent_id": agent_id,
                                "name": agent.name,
                                "type": agent.type,
                                "status": status["status"],
                                "capabilities": agent.capabilities,
                                "tasks_completed": status["tasks_completed"],
                                "last_activity": status["last_activity"]
                            }
                        )
                
                await asyncio.sleep(30)  # Sync every 30 seconds
                
            except asyncio.CancelledError:
                break
            except httpx.ConnectError:
                logger.debug("MCP server not available for sync")
                await asyncio.sleep(30)
            except Exception as e:
                logger.error("Error in MCP sync loop", error=str(e))
                await asyncio.sleep(30)
    
    async def _assign_task(self, task: dict):
        """Assign a task to an appropriate agent"""
        task_id = task.get("id")
        domain = task.get("domain")
        
        # Find suitable agent
        suitable_agent = None
        for agent_id, agent in self.agents.items():
            if agent.status.value == "idle":
                # Simple matching - in production, use more sophisticated logic
                if domain in ["finance", "analytics"] and "data_analyst" in agent.type:
                    suitable_agent = agent
                    break
                elif domain in ["integration", "api"] and "api_executor" in agent.type:
                    suitable_agent = agent
                    break
        
        if suitable_agent:
            logger.info(
                "Assigning task to agent",
                task_id=task_id,
                agent_id=suitable_agent.id,
                domain=domain
            )
            # Task assignment would be implemented here
        else:
            logger.debug(
                "No suitable agent available for task",
                task_id=task_id,
                domain=domain
            )
    
    def register_agent(self, agent: BaseAgent):
        """Register a new agent"""
        if agent.id in self.agents:
            raise ValueError(f"Agent {agent.id} already registered")
        
        self.agents[agent.id] = agent
        logger.info("Agent registered", agent_id=agent.id, agent_name=agent.name)
    
    def unregister_agent(self, agent_id: str):
        """Unregister an agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info("Agent unregistered", agent_id=agent_id)
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by ID"""
        return self.agents.get(agent_id)
    
    def get_all_agents(self) -> Dict[str, BaseAgent]:
        """Get all registered agents"""
        return self.agents.copy()
    
    def shutdown(self):
        """Signal shutdown"""
        logger.info("Shutdown signal received")
        self._shutdown_event.set()


async def health_check() -> bool:
    """Health check function for Docker HEALTHCHECK"""
    # Simple health check - in production, check actual system state
    return True


def setup_signal_handlers(agent_system: AgentSystem):
    """Setup signal handlers for graceful shutdown"""
    
    def signal_handler(sig, frame):
        logger.info("Received signal", signal=sig)
        agent_system.shutdown()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point"""
    logger.info(
        "MCP Business AI - Agent System Starting",
        version="1.0.0",
        python_version=sys.version
    )
    
    # Load configuration
    config = AgentSystemConfig()
    
    # Create agent system
    agent_system = AgentSystem(config)
    
    # Setup signal handlers
    setup_signal_handlers(agent_system)
    
    try:
        # Start the agent system
        await agent_system.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error("Fatal error in Agent System", error=str(e))
        sys.exit(1)
    finally:
        await agent_system.stop()
    
    logger.info("Agent System shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
