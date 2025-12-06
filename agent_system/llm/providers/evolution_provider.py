from typing import Dict, Any, Optional, List
import httpx
import structlog
from datetime import datetime

from agent_system.llm.providers.base_provider import BaseLLMProvider, LLMResponse

logger = structlog.get_logger()


class EvolutionProvider(BaseLLMProvider):
    """Evolution Foundation Model provider"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("evolution", config)
        
        self.api_key = config.get("api_key") if config else None
        self.base_url = config.get("base_url", "https://api.cloud.ru/evolution") if config else "https://api.cloud.ru/evolution"
        self.default_model = config.get("default_model", "evolution-llm-v1") if config else "evolution-llm-v1"
        
        # Pricing (example rates - would need actual pricing from Evolution)
        self.pricing = {
            "evolution-llm-v1": {"input": 0.001, "output": 0.002},  # per 1K tokens
            "evolution-llm-v2": {"input": 0.0015, "output": 0.003},
            "evolution-code-v1": {"input": 0.002, "output": 0.004}
        }
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        model: str = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text using Evolution Foundation Model"""
        model = model or self.default_model
        
        try:
            # Prepare request
            request_data = {
                "model": model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Make API call
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/completions",
                    json=request_data,
                    headers=headers
                )
                response.raise_for_status()
                
                result = response.json()
            
            # Extract response data
            content = result["choices"][0]["text"]
            tokens_used = result.get("usage", {}).get("total_tokens", 0)
            
            # Calculate cost
            cost = await self.estimate_cost(tokens_used, model)
            
            # Update usage stats
            self._update_usage_stats(tokens_used, cost)
            
            logger.info(
                "Evolution LLM generation successful",
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
                    "response_time": result.get("response_time"),
                    "finish_reason": result["choices"][0].get("finish_reason")
                }
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Evolution API HTTP error",
                status_code=e.response.status_code,
                error=e.response.text,
                model=model
            )
            raise Exception(f"Evolution API error: {e.response.status_code} - {e.response.text}")
        
        except Exception as e:
            logger.error(
                "Evolution LLM generation failed",
                model=model,
                error=str(e)
            )
            raise Exception(f"Evolution LLM generation failed: {str(e)}")
    
    async def generate_with_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        model: str = None,
        **kwargs
    ) -> LLMResponse:
        """Generate text using Evolution chat format"""
        model = model or self.default_model
        
        try:
            # Prepare request
            request_data = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Make API call
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=request_data,
                    headers=headers
                )
                response.raise_for_status()
                
                result = response.json()
            
            # Extract response data
            content = result["choices"][0]["message"]["content"]
            tokens_used = result.get("usage", {}).get("total_tokens", 0)
            
            # Calculate cost
            cost = await self.estimate_cost(tokens_used, model)
            
            # Update usage stats
            self._update_usage_stats(tokens_used, cost)
            
            logger.info(
                "Evolution chat generation successful",
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
                    "response_time": result.get("response_time"),
                    "finish_reason": result["choices"][0].get("finish_reason")
                }
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Evolution chat API HTTP error",
                status_code=e.response.status_code,
                error=e.response.text,
                model=model
            )
            raise Exception(f"Evolution chat API error: {e.response.status_code} - {e.response.text}")
        
        except Exception as e:
            logger.error(
                "Evolution chat generation failed",
                model=model,
                error=str(e)
            )
            raise Exception(f"Evolution chat generation failed: {str(e)}")
    
    async def get_available_models(self) -> List[str]:
        """Get list of available Evolution models"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/models",
                    headers=headers
                )
                response.raise_for_status()
                
                result = response.json()
                models = [model["id"] for model in result.get("data", [])]
                
                logger.info("Retrieved Evolution models", count=len(models))
                return models
                
        except Exception as e:
            logger.error("Failed to retrieve Evolution models", error=str(e))
            # Return default models if API call fails
            return list(self.pricing.keys())
    
    async def estimate_cost(self, tokens: int, model: str) -> float:
        """Estimate cost for token usage"""
        if model not in self.pricing:
            # Default pricing if model not found
            return tokens * 0.001 / 1000  # $0.001 per 1K tokens
        
        pricing = self.pricing[model]
        # Assume 50% input, 50% output for estimation
        input_cost = (tokens * 0.5) * pricing["input"] / 1000
        output_cost = (tokens * 0.5) * pricing["output"] / 1000
        
        return input_cost + output_cost
    
    async def validate_api_key(self) -> bool:
        """Validate the API key"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/models",
                    headers=headers
                )
                return response.status_code == 200
                
        except Exception as e:
            logger.error("API key validation failed", error=str(e))
            return False