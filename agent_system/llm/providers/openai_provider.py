from typing import Dict, Any, Optional, List
import openai
import structlog
from datetime import datetime

from agent_system.llm.providers.base_provider import BaseLLMProvider, LLMResponse

logger = structlog.get_logger()


class OpenAIProvider(BaseLLMProvider):
    """OpenAI-compatible provider"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("openai", config)
        
        self.api_key = config.get("api_key") if config else None
        self.base_url = config.get("base_url", "https://api.openai.com/v1") if config else "https://api.openai.com/v1"
        self.default_model = config.get("default_model", "gpt-3.5-turbo") if config else "gpt-3.5-turbo"
        
        # Initialize OpenAI client
        self.client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # Pricing (example rates)
        self.pricing = {
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},  # per 1K tokens
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "text-davinci-003": {"input": 0.02, "output": 0.02}
        }
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        model: str = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text using OpenAI"""
        model = model or self.default_model
        
        try:
            # Make API call
            response = await self.client.completions.create(
                model=model,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            # Extract response data
            content = response.choices[0].text
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            # Calculate cost
            cost = await self.estimate_cost(tokens_used, model)
            
            # Update usage stats
            self._update_usage_stats(tokens_used, cost)
            
            logger.info(
                "OpenAI generation successful",
                model=model,
                tokens_used=tokens_used,
                cost=cost,
                prompt_length=len(prompt)
            )
            
            return LLMResponse(
                content=content,
                model=model,
                tokens_used=tokens_used,
                cost=cost,
                metadata={
                    "prompt": prompt,
                    "parameters": {
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    },
                    "finish_reason": response.choices[0].finish_reason
                }
            )
            
        except Exception as e:
            logger.error(
                "OpenAI generation failed",
                model=model,
                error=str(e)
            )
            raise Exception(f"OpenAI generation failed: {str(e)}")
    
    async def generate_with_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        model: str = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text using OpenAI chat format"""
        model = model or self.default_model
        
        try:
            # Make API call
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            # Extract response data
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            # Calculate cost
            cost = await self.estimate_cost(tokens_used, model)
            
            # Update usage stats
            self._update_usage_stats(tokens_used, cost)
            
            logger.info(
                "OpenAI chat generation successful",
                model=model,
                tokens_used=tokens_used,
                cost=cost,
                messages_count=len(messages)
            )
            
            return LLMResponse(
                content=content,
                model=model,
                tokens_used=tokens_used,
                cost=cost,
                metadata={
                    "messages": messages,
                    "parameters": {
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    },
                    "finish_reason": response.choices[0].finish_reason
                }
            )
            
        except Exception as e:
            logger.error(
                "OpenAI chat generation failed",
                model=model,
                error=str(e)
            )
            raise Exception(f"OpenAI chat generation failed: {str(e)}")
    
    async def get_available_models(self) -> List[str]:
        """Get list of available OpenAI models"""
        try:
            models = await self.client.models.list()
            model_ids = [model.id for model in models.data]
            
            logger.info("Retrieved OpenAI models", count=len(model_ids))
            return model_ids
            
        except Exception as e:
            logger.error("Failed to retrieve OpenAI models", error=str(e))
            # Return default models if API call fails
            return list(self.pricing.keys())
    
    async def estimate_cost(self, tokens: int, model: str) -> float:
        """Estimate cost for token usage"""
        if model not in self.pricing:
            # Default pricing if model not found
            return tokens * 0.002 / 1000  # $0.002 per 1K tokens
        
        pricing = self.pricing[model]
        # Assume 50% input, 50% output for estimation
        input_cost = (tokens * 0.5) * pricing["input"] / 1000
        output_cost = (tokens * 0.5) * pricing["output"] / 1000
        
        return input_cost + output_cost
    
    async def validate_api_key(self) -> bool:
        """Validate the API key"""
        try:
            await self.client.models.list()
            return True
        except Exception as e:
            logger.error("OpenAI API key validation failed", error=str(e))
            return False