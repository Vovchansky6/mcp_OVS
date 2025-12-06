from pydantic_settings import BaseSettings
from typing import Optional, List
import os


class Settings(BaseSettings):
    # App Configuration
    app_name: str = "MCP Business AI Server"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost/mcp_db"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_cache_ttl: int = 3600
    
    # External APIs
    evolution_api_key: Optional[str] = None
    evolution_base_url: str = "https://api.cloud.ru/evolution"
    openai_api_key: Optional[str] = None
    huggingface_api_key: Optional[str] = None
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    
    # Circuit Breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 30
    
    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 9090
    jaeger_endpoint: Optional[str] = None
    
    # LLM Configuration
    default_llm_provider: str = "evolution"
    max_tokens: int = 4000
    temperature: float = 0.7
    
    # Agent Configuration
    max_concurrent_agents: int = 10
    agent_timeout: int = 300
    
    # Business Logic
    supported_business_domains: List[str] = [
        "finance", "healthcare", "retail", "manufacturing", "technology"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()