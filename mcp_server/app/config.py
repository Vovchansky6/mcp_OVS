from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application configuration for MCP server"""

    # App Configuration
    app_name: str = "MCP Business AI Server"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # Database & Cache
    # Эти значения перекрываются переменными окружения:
    # DATABASE_URL, REDIS_URL
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/mcp_db"
    redis_url: str = "redis://localhost:6379"

    # Security / Auth
    # SECRET_KEY переопределяется переменной окружения SECRET_KEY
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # Agent Configuration
    max_concurrent_agents: int = 10
    agent_timeout: int = 300  # seconds

    # Business Logic
    supported_business_domains: List[str] = [
        "finance",
        "healthcare",
        "retail",
        "manufacturing",
        "technology",
    ]

    # External Go business engine
    # Перекрывается переменной окружения GO_BIZ_ENGINE_URL, GO_BIZ_ENGINE_TIMEOUT
    go_biz_engine_url: str = "http://localhost:8080"
    go_biz_engine_timeout: int = 10  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
