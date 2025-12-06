from typing import Dict, Any, Optional
import asyncio
import structlog
from datetime import datetime
import httpx

from agent_system.core.base_agent import BaseAgent, AgentMessage, MessageType
from app.core.models.mcp_protocol import BusinessTask

logger = structlog.get_logger()


class APIExecutorAgent(BaseAgent):
    """Specialized agent for executing external API calls"""
    
    def __init__(self, agent_id: str, config: Dict[str, Any] = None):
        super().__init__(
            agent_id=agent_id,
            name="API Executor",
            agent_type="api_executor",
            capabilities=[
                "api_calls",
                "data_retrieval",
                "webhook_execution",
                "api_monitoring",
                "rate_limiting",
                "error_handling"
            ],
            config=config
        )
        
        self.api_configs = config.get("api_configs", {}) if config else {}
        self.rate_limits = {}
        self.circuit_breakers = {}
    
    async def process_task(self, task: BusinessTask) -> Dict[str, Any]:
        """Process API execution task"""
        logger.info(
            "Processing API execution task",
            agent_id=self.id,
            task_id=task.id,
            task_title=task.title
        )
        
        try:
            input_data = task.input_data or {}
            api_calls = input_data.get("api_calls", [])
            
            if not api_calls:
                raise Exception("No API calls specified in task")
            
            results = []
            
            # Execute API calls
            for api_call in api_calls:
                result = await self._execute_api_call(api_call)
                results.append(result)
                
                # Add delay between calls to respect rate limits
                await asyncio.sleep(0.1)
            
            # Aggregate results
            aggregated_result = await self._aggregate_results(results)
            
            return {
                "api_calls_executed": len(api_calls),
                "results": results,
                "aggregated_result": aggregated_result,
                "metadata": {
                    "executed_at": datetime.utcnow().isoformat(),
                    "total_execution_time": sum(r.get("execution_time", 0) for r in results),
                    "success_rate": sum(1 for r in results if r.get("success", False)) / len(results)
                }
            }
            
        except Exception as e:
            logger.error(
                "API execution task failed",
                agent_id=self.id,
                task_id=task.id,
                error=str(e)
            )
            raise
    
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle incoming messages"""
        if message.message_type == MessageType.STATUS_UPDATE:
            return None
        elif message.message_type == MessageType.ERROR:
            logger.warning(
                "Received error message",
                agent_id=self.id,
                sender_id=message.sender_id,
                error=message.payload.get("error")
            )
            return None
        
        return None
    
    async def _execute_api_call(self, api_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single API call"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Extract API call details
            api_name = api_call.get("api_name")
            method = api_call.get("method", "GET").upper()
            url = api_call.get("url")
            headers = api_call.get("headers", {})
            params = api_call.get("params", {})
            data = api_call.get("data", {})
            
            if not url:
                raise Exception("URL is required for API call")
            
            # Check rate limits
            if not await self._check_rate_limit(api_name):
                raise Exception(f"Rate limit exceeded for API: {api_name}")
            
            # Check circuit breaker
            if not await self._check_circuit_breaker(api_name):
                raise Exception(f"Circuit breaker open for API: {api_name}")
            
            # Execute API call
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=data if method in ["POST", "PUT", "PATCH"] else None
                )
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            # Update rate limit
            await self._update_rate_limit(api_name)
            
            # Update circuit breaker
            await self._update_circuit_breaker(api_name, response.status_code < 400)
            
            # Process response
            result = {
                "api_name": api_name,
                "method": method,
                "url": url,
                "status_code": response.status_code,
                "success": 200 <= response.status_code < 300,
                "execution_time": execution_time,
                "response_headers": dict(response.headers),
                "response_data": None
            }
            
            # Parse response data
            try:
                if response.headers.get("content-type", "").startswith("application/json"):
                    result["response_data"] = response.json()
                else:
                    result["response_data"] = response.text
            except Exception:
                result["response_data"] = response.text
            
            logger.info(
                "API call executed successfully",
                agent_id=self.id,
                api_name=api_name,
                status_code=response.status_code,
                execution_time=execution_time
            )
            
            return result
            
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            
            # Update circuit breaker for failure
            await self._update_circuit_breaker(api_name, False)
            
            logger.error(
                "API call failed",
                agent_id=self.id,
                api_name=api_call.get("api_name"),
                error=str(e),
                execution_time=execution_time
            )
            
            return {
                "api_name": api_call.get("api_name"),
                "method": api_call.get("method", "GET"),
                "url": api_call.get("url"),
                "success": False,
                "execution_time": execution_time,
                "error": str(e)
            }
    
    async def _check_rate_limit(self, api_name: str) -> bool:
        """Check if API call is allowed by rate limit"""
        if not api_name:
            return True
        
        now = asyncio.get_event_loop().time()
        window_start = now - 60  # 1-minute window
        
        # Get recent calls for this API
        recent_calls = [
            call_time for call_time in self.rate_limits.get(api_name, [])
            if call_time > window_start
        ]
        
        # Check limit (default: 60 calls per minute)
        limit = self.api_configs.get(api_name, {}).get("rate_limit", 60)
        
        if len(recent_calls) >= limit:
            return False
        
        return True
    
    async def _update_rate_limit(self, api_name: str):
        """Update rate limit tracking"""
        if not api_name:
            return
        
        now = asyncio.get_event_loop().time()
        
        if api_name not in self.rate_limits:
            self.rate_limits[api_name] = []
        
        self.rate_limits[api_name].append(now)
        
        # Clean up old entries (older than 1 minute)
        window_start = now - 60
        self.rate_limits[api_name] = [
            call_time for call_time in self.rate_limits[api_name]
            if call_time > window_start
        ]
    
    async def _check_circuit_breaker(self, api_name: str) -> bool:
        """Check if circuit breaker allows API call"""
        if not api_name:
            return True
        
        breaker_state = self.circuit_breakers.get(api_name, {
            "failures": 0,
            "last_failure": None,
            "state": "closed"  # closed, open, half_open
        })
        
        if breaker_state["state"] == "open":
            # Check if we should try half-open
            if breaker_state["last_failure"]:
                time_since_failure = asyncio.get_event_loop().time() - breaker_state["last_failure"]
                if time_since_failure > 30:  # 30-second timeout
                    breaker_state["state"] = "half_open"
                else:
                    return False
        
        return True
    
    async def _update_circuit_breaker(self, api_name: str, success: bool):
        """Update circuit breaker state based on API call result"""
        if not api_name:
            return
        
        if api_name not in self.circuit_breakers:
            self.circuit_breakers[api_name] = {
                "failures": 0,
                "last_failure": None,
                "state": "closed"
            }
        
        breaker_state = self.circuit_breakers[api_name]
        
        if success:
            # Reset on success
            breaker_state["failures"] = 0
            breaker_state["state"] = "closed"
        else:
            # Increment failures
            breaker_state["failures"] += 1
            breaker_state["last_failure"] = asyncio.get_event_loop().time()
            
            # Open circuit if too many failures
            if breaker_state["failures"] >= 5:
                breaker_state["state"] = "open"
    
    async def _aggregate_results(self, results: list) -> Dict[str, Any]:
        """Aggregate results from multiple API calls"""
        successful_calls = [r for r in results if r.get("success", False)]
        failed_calls = [r for r in results if not r.get("success", False)]
        
        total_execution_time = sum(r.get("execution_time", 0) for r in results)
        
        # Extract data from successful calls
        aggregated_data = {}
        for result in successful_calls:
            api_name = result.get("api_name")
            response_data = result.get("response_data")
            if response_data:
                aggregated_data[api_name] = response_data
        
        return {
            "total_calls": len(results),
            "successful_calls": len(successful_calls),
            "failed_calls": len(failed_calls),
            "success_rate": len(successful_calls) / len(results) if results else 0,
            "total_execution_time": total_execution_time,
            "average_execution_time": total_execution_time / len(results) if results else 0,
            "aggregated_data": aggregated_data,
            "errors": [r.get("error") for r in failed_calls if r.get("error")]
        }