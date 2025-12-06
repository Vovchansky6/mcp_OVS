from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import structlog
from datetime import datetime

logger = structlog.get_logger()


class LLMResponse:
    """Response from LLM provider"""
    
    def __init__(
        self,
        content: str,
        model: str,
        tokens_used: int,
        cost: float,
        metadata: Dict[str, Any] = None
    ):
        self.content = content
        self.model = model
        self.tokens_used = tokens_used
        self.cost = cost
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, provider_name: str, config: Dict[str, Any] = None):
        self.provider_name = provider_name
        self.config = config or {}
        self.total_tokens_used = 0
        self.total_cost = 0.0
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Generate text using the LLM"""
        pass
    
    @abstractmethod
    async def generate_with_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Generate text using chat format"""
        pass
    
    @abstractmethod
    async def get_available_models(self) -> List[str]:
        """Get list of available models"""
        pass
    
    @abstractmethod
    async def estimate_cost(self, tokens: int, model: str) -> float:
        """Estimate cost for token usage"""
        pass
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "provider": self.provider_name,
            "total_tokens_used": self.total_tokens_used,
            "total_cost": self.total_cost,
            "average_cost_per_token": self.total_cost / self.total_tokens_used if self.total_tokens_used > 0 else 0
        }
    
    def _update_usage_stats(self, tokens_used: int, cost: float):
        """Update usage statistics"""
        self.total_tokens_used += tokens_used
        self.total_cost += cost
        
        logger.info(
            "LLM usage updated",
            provider=self.provider_name,
            tokens_used=tokens_used,
            cost=cost,
            total_tokens=self.total_tokens_used,
            total_cost=self.total_cost
        )