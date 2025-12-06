from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import asyncio
import uuid
import structlog
from datetime import datetime
from enum import Enum

from app.core.models.mcp_protocol import AgentStatus, BusinessTask

logger = structlog.get_logger()


class MessageType(Enum):
    TASK_ASSIGNMENT = "task_assignment"
    TASK_RESULT = "task_result"
    STATUS_UPDATE = "status_update"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class AgentMessage:
    """Message for agent communication"""
    
    def __init__(
        self,
        sender_id: str,
        recipient_id: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None
    ):
        self.id = str(uuid.uuid4())
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.message_type = message_type
        self.payload = payload
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.timestamp = datetime.utcnow()


class BaseAgent(ABC):
    """Abstract base class for all agents"""
    
    def __init__(
        self,
        agent_id: str,
        name: str,
        agent_type: str,
        capabilities: List[str],
        config: Dict[str, Any] = None
    ):
        self.id = agent_id
        self.name = name
        self.type = agent_type
        self.capabilities = capabilities
        self.config = config or {}
        self.status = AgentStatus.IDLE
        self.current_task = None
        self.tasks_completed = 0
        self.last_activity = datetime.utcnow()
        self.message_queue = asyncio.Queue()
        self._running = False
        self._task_handler = None
        
        logger.info(
            "Agent initialized",
            agent_id=agent_id,
            name=name,
            type=agent_type,
            capabilities=capabilities
        )
    
    async def start(self):
        """Start the agent"""
        if self._running:
            logger.warning("Agent already running", agent_id=self.id)
            return
        
        self._running = True
        self._task_handler = asyncio.create_task(self._message_loop())
        
        logger.info("Agent started", agent_id=self.id)
        
        # Send startup notification
        await self._send_status_update()
    
    async def stop(self):
        """Stop the agent"""
        if not self._running:
            logger.warning("Agent not running", agent_id=self.id)
            return
        
        self._running = False
        
        if self._task_handler:
            self._task_handler.cancel()
            try:
                await self._task_handler
            except asyncio.CancelledError:
                pass
        
        logger.info("Agent stopped", agent_id=self.id)
    
    async def send_message(self, message: AgentMessage):
        """Send a message to this agent"""
        await self.message_queue.put(message)
    
    async def assign_task(self, task: BusinessTask):
        """Assign a task to this agent"""
        if self.status != AgentStatus.IDLE:
            raise Exception(f"Agent {self.id} is not idle (status: {self.status})")
        
        self.current_task = task
        self.status = AgentStatus.PROCESSING
        self.last_activity = datetime.utcnow()
        
        logger.info(
            "Task assigned to agent",
            agent_id=self.id,
            task_id=task.id,
            task_title=task.title
        )
        
        # Send task assignment message
        message = AgentMessage(
            sender_id="system",
            recipient_id=self.id,
            message_type=MessageType.TASK_ASSIGNMENT,
            payload={"task": task.dict()}
        )
        await self.send_message(message)
    
    @abstractmethod
    async def process_task(self, task: BusinessTask) -> Dict[str, Any]:
        """Process a business task - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle incoming message - must be implemented by subclasses"""
        pass
    
    async def _message_loop(self):
        """Main message processing loop"""
        logger.info("Agent message loop started", agent_id=self.id)
        
        while self._running:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                
                await self._process_message(message)
                
            except asyncio.TimeoutError:
                # Send periodic heartbeat
                if self._running:
                    await self._send_heartbeat()
            except Exception as e:
                logger.error(
                    "Error in agent message loop",
                    agent_id=self.id,
                    error=str(e)
                )
        
        logger.info("Agent message loop stopped", agent_id=self.id)
    
    async def _process_message(self, message: AgentMessage):
        """Process an incoming message"""
        try:
            logger.debug(
                "Processing message",
                agent_id=self.id,
                message_type=message.message_type.value,
                sender_id=message.sender_id
            )
            
            # Handle different message types
            if message.message_type == MessageType.TASK_ASSIGNMENT:
                await self._handle_task_assignment(message)
            elif message.message_type == MessageType.STATUS_UPDATE:
                await self._handle_status_update(message)
            elif message.message_type == MessageType.ERROR:
                await self._handle_error_message(message)
            else:
                # Delegate to subclass for custom handling
                response = await self.handle_message(message)
                if response:
                    await self._send_message(response)
            
            self.last_activity = datetime.utcnow()
            
        except Exception as e:
            logger.error(
                "Error processing message",
                agent_id=self.id,
                message_id=message.id,
                error=str(e)
            )
            
            # Send error response
            error_message = AgentMessage(
                sender_id=self.id,
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                payload={"error": str(e), "original_message_id": message.id},
                correlation_id=message.correlation_id
            )
            await self._send_message(error_message)
    
    async def _handle_task_assignment(self, message: AgentMessage):
        """Handle task assignment message"""
        task_data = message.payload.get("task")
        if not task_data:
            raise Exception("No task data in assignment message")
        
        # Convert to BusinessTask object
        task = BusinessTask(**task_data)
        
        try:
            # Process the task
            result = await self.process_task(task)
            
            # Mark task as completed
            self.current_task = None
            self.status = AgentStatus.IDLE
            self.tasks_completed += 1
            
            # Send success response
            response = AgentMessage(
                sender_id=self.id,
                recipient_id=message.sender_id,
                message_type=MessageType.TASK_RESULT,
                payload={
                    "task_id": task.id,
                    "status": "completed",
                    "result": result
                },
                correlation_id=message.correlation_id
            )
            await self._send_message(response)
            
            logger.info(
                "Task completed successfully",
                agent_id=self.id,
                task_id=task.id
            )
            
        except Exception as e:
            # Mark task as failed
            self.current_task = None
            self.status = AgentStatus.ERROR
            
            # Send error response
            response = AgentMessage(
                sender_id=self.id,
                recipient_id=message.sender_id,
                message_type=MessageType.TASK_RESULT,
                payload={
                    "task_id": task.id,
                    "status": "failed",
                    "error": str(e)
                },
                correlation_id=message.correlation_id
            )
            await self._send_message(response)
            
            logger.error(
                "Task failed",
                agent_id=self.id,
                task_id=task.id,
                error=str(e)
            )
    
    async def _handle_status_update(self, message: AgentMessage):
        """Handle status update message"""
        # Default implementation - can be overridden
        logger.debug(
            "Received status update",
            agent_id=self.id,
            sender_id=message.sender_id,
            payload=message.payload
        )
    
    async def _handle_error_message(self, message: AgentMessage):
        """Handle error message"""
        logger.error(
            "Received error message",
            agent_id=self.id,
            sender_id=message.sender_id,
            error=message.payload.get("error")
        )
    
    async def _send_heartbeat(self):
        """Send heartbeat message"""
        heartbeat = AgentMessage(
            sender_id=self.id,
            recipient_id="system",
            message_type=MessageType.HEARTBEAT,
            payload={
                "status": self.status.value,
                "current_task_id": self.current_task.id if self.current_task else None,
                "tasks_completed": self.tasks_completed,
                "last_activity": self.last_activity.isoformat()
            }
        )
        await self._send_message(heartbeat)
    
    async def _send_status_update(self):
        """Send status update message"""
        status_update = AgentMessage(
            sender_id=self.id,
            recipient_id="system",
            message_type=MessageType.STATUS_UPDATE,
            payload={
                "status": self.status.value,
                "capabilities": self.capabilities,
                "config": self.config
            }
        )
        await self._send_message(status_update)
    
    async def _send_message(self, message: AgentMessage):
        """Send message through the message bus"""
        # This would typically send through a message bus
        # For now, we'll just log it
        logger.debug(
            "Sending message",
            agent_id=self.id,
            recipient_id=message.recipient_id,
            message_type=message.message_type.value
        )
        
        # In a real implementation, this would use the MessageBus
        # await message_bus.send(message)
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status information"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "status": self.status.value,
            "capabilities": self.capabilities,
            "current_task_id": self.current_task.id if self.current_task else None,
            "tasks_completed": self.tasks_completed,
            "last_activity": self.last_activity.isoformat(),
            "running": self._running
        }