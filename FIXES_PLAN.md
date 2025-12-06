# Детальный план исправлений критических недоработок

## Приоритеты
- 🔴 **КРИТИЧНО** - Блокирует работу системы
- 🟠 **ВЫСОКИЙ** - Серьезно влияет на функциональность
- 🟡 **СРЕДНИЙ** - Важно для production, но не блокирует
- 🟢 **НИЗКИЙ** - Улучшения и оптимизации

---

## 🔴 КРИТИЧНО: Подключение к PostgreSQL

### Проблема
- Нет реального подключения к БД
- Данные хранятся только в памяти
- При перезапуске все данные теряются

### Решение

#### Шаг 1: Создать модуль подключения к БД
**Файл:** `mcp_server/app/core/database.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
import structlog

logger = structlog.get_logger()

Base = declarative_base()

# Создать async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Создать session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db() -> AsyncSession:
    """Dependency для получения DB session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Инициализация БД - создание таблиц"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

async def close_db():
    """Закрытие соединений с БД"""
    await engine.dispose()
    logger.info("Database connections closed")
```

#### Шаг 2: Создать модели SQLAlchemy
**Файл:** `mcp_server/app/core/models/database.py`

```python
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey, Boolean, ARRAY, DECIMAL
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class Tool(Base):
    __tablename__ = "tools"
    __table_args__ = {"schema": "mcp"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    input_schema = Column(JSON, nullable=False, default={})
    status = Column(String(50), default='active')
    category = Column(String(100))
    tags = Column(ARRAY(String))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = {"schema": "agents"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    type = Column(String(100), nullable=False)
    description = Column(Text)
    capabilities = Column(ARRAY(String), default=[])
    status = Column(String(50), default='idle')
    current_task_id = Column(UUID(as_uuid=True), ForeignKey('agents.tasks.id'))
    tasks_completed = Column(Integer, default=0)
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    config = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = {"schema": "agents"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    domain = Column(String(100), nullable=False)
    priority = Column(String(50), default='medium')
    status = Column(String(50), default='pending')
    agent_id = Column(UUID(as_uuid=True), ForeignKey('agents.agents.id'))
    input_data = Column(JSON, default={})
    output_data = Column(JSON)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

class ToolExecution(Base):
    __tablename__ = "tool_executions"
    __table_args__ = {"schema": "mcp"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_name = Column(String(255), nullable=False)
    agent_id = Column(UUID(as_uuid=True))
    task_id = Column(UUID(as_uuid=True))
    parameters = Column(JSON, nullable=False, default={})
    result = Column(JSON)
    error = Column(Text)
    execution_time_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

#### Шаг 3: Обновить main.py для инициализации БД
**Файл:** `mcp_server/app/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting MCP Business AI Server", version=settings.app_version)
    
    # Initialize services
    try:
        # Инициализация БД
        await init_db()
        logger.info("Database initialized successfully")
        
        # Здесь можно добавить инициализацию Redis
        # await init_redis()
        
    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise
    
    yield
    
    # Cleanup
    await close_db()
    logger.info("Shutting down MCP Business AI Server")
```

#### Шаг 4: Обновить TaskOrchestrator для работы с БД
**Файл:** `mcp_server/app/core/services/task_orchestrator.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.models.database import Task as TaskModel
from app.core.models.mcp_protocol import BusinessTask, TaskRequest, TaskResponse

class TaskOrchestrator:
    """Orchestrates task execution across agents"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.agent_registry = AgentRegistry()
    
    async def create_task(self, request: TaskRequest) -> TaskResponse:
        """Create and assign a new business task"""
        # Создать задачу в БД
        db_task = TaskModel(
            title=request.title,
            description=request.description,
            domain=request.domain,
            priority=request.priority,
            input_data=request.input_data,
            status="pending"
        )
        self.db.add(db_task)
        await self.db.flush()
        
        # Найти подходящего агента
        agent_id = await self._find_suitable_agent(db_task)
        
        if agent_id:
            # Обновить задачу
            db_task.agent_id = agent_id
            db_task.status = "processing"
            db_task.started_at = datetime.utcnow()
            
            await self.db.commit()
            
            return TaskResponse(
                task_id=str(db_task.id),
                status="processing",
                agent_id=str(agent_id),
                estimated_completion_time=datetime.utcnow() + timedelta(minutes=30)
            )
        
        await self.db.commit()
        return TaskResponse(
            task_id=str(db_task.id),
            status="pending",
            agent_id=None
        )
    
    async def get_task(self, task_id: str) -> Optional[BusinessTask]:
        """Get task by ID"""
        result = await self.db.execute(
            select(TaskModel).where(TaskModel.id == task_id)
        )
        db_task = result.scalar_one_or_none()
        if not db_task:
            return None
        
        # Конвертировать в BusinessTask
        return BusinessTask(
            id=str(db_task.id),
            title=db_task.title,
            description=db_task.description,
            domain=db_task.domain,
            priority=db_task.priority,
            status=db_task.status,
            agent_id=str(db_task.agent_id) if db_task.agent_id else None,
            input_data=db_task.input_data,
            output_data=db_task.output_data,
            created_at=db_task.created_at,
            started_at=db_task.started_at,
            completed_at=db_task.completed_at,
            error_message=db_task.error_message
        )
```

**Оценка времени:** 4-6 часов  
**Зависимости:** Нет

---

## 🔴 КРИТИЧНО: Подключение к Redis

### Проблема
- Rate limiting работает только в памяти
- Не масштабируется на несколько инстансов
- Нет кеширования

### Решение

#### Шаг 1: Создать модуль Redis
**Файл:** `mcp_server/app/core/redis_client.py`

```python
import redis.asyncio as redis
from app.config import settings
import structlog
import json

logger = structlog.get_logger()

class RedisClient:
    """Async Redis client wrapper"""
    
    def __init__(self):
        self.client: redis.Redis = None
        self.url = settings.redis_url
    
    async def connect(self):
        """Подключиться к Redis"""
        try:
            self.client = await redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50
            )
            # Проверка подключения
            await self.client.ping()
            logger.info("Redis connected successfully", url=self.url)
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def disconnect(self):
        """Отключиться от Redis"""
        if self.client:
            await self.client.close()
            logger.info("Redis disconnected")
    
    async def get(self, key: str) -> str:
        """Получить значение"""
        return await self.client.get(key)
    
    async def set(self, key: str, value: str, ttl: int = None):
        """Установить значение"""
        if ttl:
            await self.client.setex(key, ttl, value)
        else:
            await self.client.set(key, value)
    
    async def delete(self, key: str):
        """Удалить ключ"""
        await self.client.delete(key)
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Увеличить значение"""
        return await self.client.incrby(key, amount)
    
    async def expire(self, key: str, seconds: int):
        """Установить TTL"""
        await self.client.expire(key, seconds)
    
    async def zadd(self, key: str, score: float, member: str):
        """Добавить в sorted set"""
        await self.client.zadd(key, {member: score})
    
    async def zrange(self, key: str, start: int, end: int) -> list:
        """Получить диапазон из sorted set"""
        return await self.client.zrange(key, start, end)
    
    async def zremrangebyscore(self, key: str, min_score: float, max_score: float):
        """Удалить элементы по score"""
        await self.client.zremrangebyscore(key, min_score, max_score)
    
    async def zcard(self, key: str) -> int:
        """Получить количество элементов в sorted set"""
        return await self.client.zcard(key)

# Глобальный экземпляр
redis_client = RedisClient()
```

#### Шаг 2: Обновить RateLimitingMiddleware
**Файл:** `mcp_server/app/middleware/rate_limiting.py`

```python
from app.core.redis_client import redis_client
import time

class RateLimitingMiddleware:
    """Rate limiting middleware using Redis-based sliding window"""
    
    async def __call__(self, request: Request, call_next):
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Check rate limit using Redis
        if not await self._check_rate_limit(client_id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(settings.rate_limit_window)}
            )
        
        # Record request
        await self._record_request(client_id)
        
        return await call_next(request)
    
    async def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client has exceeded rate limit using Redis"""
        now = time.time()
        window_start = now - settings.rate_limit_window
        
        # Использовать Redis sorted set для sliding window
        key = f"rate_limit:{client_id}"
        
        # Удалить старые записи
        await redis_client.zremrangebyscore(key, 0, window_start)
        
        # Подсчитать количество запросов в окне
        count = await redis_client.zcard(key)
        
        if count >= settings.rate_limit_requests:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                request_count=count,
                limit=settings.rate_limit_requests
            )
            return False
        
        return True
    
    async def _record_request(self, client_id: str):
        """Record a request for rate limiting in Redis"""
        now = time.time()
        key = f"rate_limit:{client_id}"
        
        # Добавить текущий запрос
        await redis_client.zadd(key, now, str(now))
        
        # Установить TTL для автоматической очистки
        await redis_client.expire(key, settings.rate_limit_window)
```

#### Шаг 3: Инициализировать Redis в main.py
**Файл:** `mcp_server/app/main.py`

```python
from app.core.redis_client import redis_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting MCP Business AI Server", version=settings.app_version)
    
    try:
        await init_db()
        await redis_client.connect()  # Добавить инициализацию Redis
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise
    
    yield
    
    await redis_client.disconnect()  # Закрыть соединение
    await close_db()
    logger.info("Shutting down MCP Business AI Server")
```

**Оценка времени:** 3-4 часа  
**Зависимости:** Нет

---

## 🔴 КРИТИЧНО: Исправление проблем безопасности

### Проблема
- Дефолтный секретный ключ в коде
- Хардкод API ключей
- Нет проверки API ключей в БД

### Решение

#### Шаг 1: Обновить config.py
**Файл:** `mcp_server/app/config.py`

```python
from pydantic_settings import BaseSettings
from typing import Optional
import secrets

class Settings(BaseSettings):
    # Security - ОБЯЗАТЕЛЬНЫЕ переменные окружения
    secret_key: str  # Должен быть установлен через .env
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Валидация
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.secret_key == "your-secret-key-change-in-production":
            raise ValueError(
                "SECRET_KEY must be set in environment variables. "
                "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

#### Шаг 2: Создать модель API ключей в БД
**Файл:** `mcp_server/app/core/models/database.py` (добавить)

```python
class APIKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = {"schema": "mcp"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash = Column(String(255), unique=True, nullable=False)  # Хеш ключа
    name = Column(String(255), nullable=False)
    user_id = Column(UUID(as_uuid=True))
    permissions = Column(ARRAY(String), default=['read', 'write'])
    rate_limit = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
```

#### Шаг 3: Обновить AuthMiddleware
**Файл:** `mcp_server/app/middleware/auth.py`

```python
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.models.database import APIKey
from app.core.database import get_db
from datetime import datetime

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthMiddleware:
    """Authentication middleware for JWT and API key authentication"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def _verify_api_key(self, api_key: str) -> bool:
        """Verify API key against database"""
        # Хешировать ключ для поиска
        key_hash = pwd_context.hash(api_key)
        
        # Искать в БД
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.key_hash == key_hash,
                APIKey.is_active == True
            )
        )
        db_key = result.scalar_one_or_none()
        
        if not db_key:
            return False
        
        # Проверить срок действия
        if db_key.expires_at and db_key.expires_at < datetime.utcnow():
            return False
        
        # Обновить last_used
        db_key.last_used = datetime.utcnow()
        await self.db.commit()
        
        return True
```

#### Шаг 4: Создать утилиту для генерации API ключей
**Файл:** `mcp_server/app/utils/security.py`

```python
import secrets
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_api_key() -> str:
    """Генерировать новый API ключ"""
    return f"mcp_{secrets.token_urlsafe(32)}"

def hash_api_key(key: str) -> str:
    """Хешировать API ключ для хранения"""
    return pwd_context.hash(key)

def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Проверить API ключ"""
    return pwd_context.verify(plain_key, hashed_key)
```

**Оценка времени:** 2-3 часа  
**Зависимости:** Модуль БД должен быть готов

---

## 🔴 КРИТИЧНО: Реализация MCP протокола

### Проблема
- Методы возвращают пустые результаты
- Нет реальной работы с tools и resources

### Решение

#### Шаг 1: Обновить handle_tools_list
**Файл:** `mcp_server/app/main.py`

```python
async def handle_tools_list(message: Dict[str, Any], correlation_id: str):
    """Handle tools list request"""
    from app.core.services.tool_registry import ToolRegistry
    from app.core.database import get_db
    
    async for db in get_db():
        tool_registry = ToolRegistry(db)
        tools = await tool_registry.get_all_tools()
        
        # Конвертировать в MCP формат
        mcp_tools = []
        for tool_name, tool in tools.items():
            mcp_tools.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema
            })
        
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "tools": mcp_tools
            }
        }
```

#### Шаг 2: Обновить handle_tools_call
**Файл:** `mcp_server/app/main.py`

```python
async def handle_tools_call(message: Dict[str, Any], correlation_id: str):
    """Handle tool execution request"""
    from app.core.services.tool_registry import ToolRegistry
    from app.core.database import get_db
    
    params = message.get("params", {})
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    if not tool_name:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32602,
                "message": "Invalid params: tool name required"
            }
        }
    
    async for db in get_db():
        tool_registry = ToolRegistry(db)
        
        try:
            execution = await tool_registry.execute_tool(
                tool_name,
                arguments,
                agent_id=None  # Можно получить из контекста
            )
            
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": str(execution.result) if execution.result else ""
                        }
                    ],
                    "isError": execution.error is not None
                }
            }
        except Exception as e:
            logger.error("Tool execution failed", tool=tool_name, error=str(e))
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Tool execution failed: {str(e)}"
                }
            }
```

#### Шаг 3: Реализовать handle_resources_list и handle_resources_read
**Файл:** `mcp_server/app/main.py`

```python
async def handle_resources_list(message: Dict[str, Any], correlation_id: str):
    """Handle resources list request"""
    from app.core.services.resource_registry import ResourceRegistry
    from app.core.database import get_db
    
    async for db in get_db():
        resource_registry = ResourceRegistry(db)
        resources = await resource_registry.list_resources()
        
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "resources": [
                    {
                        "uri": res.uri,
                        "name": res.name,
                        "description": res.description,
                        "mimeType": res.mime_type
                    }
                    for res in resources
                ]
            }
        }

async def handle_resources_read(message: Dict[str, Any], correlation_id: str):
    """Handle resource read request"""
    from app.core.services.resource_registry import ResourceRegistry
    from app.core.database import get_db
    
    params = message.get("params", {})
    uri = params.get("uri")
    
    if not uri:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32602,
                "message": "Invalid params: resource URI required"
            }
        }
    
    async for db in get_db():
        resource_registry = ResourceRegistry(db)
        resource = await resource_registry.get_resource(uri)
        
        if not resource:
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Resource not found: {uri}"
                }
            }
        
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "contents": [
                    {
                        "uri": resource.uri,
                        "mimeType": resource.mime_type,
                        "text": resource.content  # Загрузить содержимое
                    }
                ]
            }
        }
```

**Оценка времени:** 4-5 часов  
**Зависимости:** Модуль БД, ToolRegistry должен быть обновлен

---

## 🟠 ВЫСОКИЙ: Исправление Agent Registry

### Проблема
- Создание агента без ID
- Обращение к current_task.id без проверки

### Решение

#### Шаг 1: Исправить создание агента
**Файл:** `mcp_server/app/core/services/agent_registry.py`

```python
async def create_agent(self, request: AgentRequest) -> Agent:
    """Create a new agent"""
    async with self._lock:
        if request.type not in self.agent_types:
            raise ValueError(f"Unknown agent type: {request.type}")
        
        # Генерировать ID перед созданием
        agent_id = str(uuid.uuid4())
        
        agent_class = self.agent_types[request.type]
        agent = agent_class(
            agent_id=agent_id,  # Передать ID
            name=request.name,
            agent_type=request.type,
            capabilities=request.capabilities,
            config=request.config
        )
        
        # Сохранить в БД
        db_agent = AgentModel(
            id=agent_id,
            name=request.name,
            type=request.type,
            description=request.description,
            capabilities=request.capabilities,
            config=request.config,
            status="idle"
        )
        self.db.add(db_agent)
        await self.db.commit()
        
        # Сохранить в памяти
        self.agents[agent.id] = agent
        
        # Запустить агента
        await agent.start()
        
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
```

#### Шаг 2: Исправить обращение к current_task
**Файл:** `mcp_server/app/core/services/agent_registry.py`

```python
async def get_agent(self, agent_id: str) -> Optional[Agent]:
    """Get agent by ID"""
    async with self._lock:
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        
        # Безопасное получение current_task_id
        current_task_id = None
        if agent.current_task:
            current_task_id = str(agent.current_task.id)
        
        return Agent(
            id=agent.id,
            name=agent.name,
            type=agent.type,
            description="",
            capabilities=agent.capabilities,
            status=agent.status,
            current_task_id=current_task_id,  # Использовать безопасное значение
            tasks_completed=agent.tasks_completed,
            last_activity=agent.last_activity,
            config=agent.config
        )
```

**Оценка времени:** 1-2 часа  
**Зависимости:** Нет

---

## 🟠 ВЫСОКИЙ: Реальная интеграция с LLM

### Проблема
- Tools только симулируют работу
- LLM провайдеры не используются в tools

### Решение

#### Шаг 1: Обновить ToolRegistry для использования LLM
**Файл:** `mcp_server/app/core/services/tool_registry.py`

```python
from agent_system.llm.providers.evolution_provider import EvolutionProvider
from agent_system.llm.providers.openai_provider import OpenAIProvider
from app.config import settings

class ToolRegistry:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tools: Dict[str, MCPTool] = {}
        self.executions: List[ToolExecution] = []
        self._lock = asyncio.Lock()
        
        # Инициализировать LLM провайдеры
        self.llm_providers = {}
        if settings.evolution_api_key:
            self.llm_providers["evolution"] = EvolutionProvider({
                "api_key": settings.evolution_api_key
            })
        if settings.openai_api_key:
            self.llm_providers["openai"] = OpenAIProvider({
                "api_key": settings.openai_api_key
            })
    
    async def _execute_llm_processor(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute LLM processing tool with real LLM"""
        prompt = parameters.get("prompt")
        if not prompt:
            raise ValueError("Prompt is required")
        
        # Выбрать провайдера
        provider_name = parameters.get("provider", settings.default_llm_provider)
        provider = self.llm_providers.get(provider_name)
        
        if not provider:
            raise ValueError(f"LLM provider '{provider_name}' not available")
        
        # Вызвать LLM
        response = await provider.generate(
            prompt=prompt,
            max_tokens=parameters.get("max_tokens", settings.max_tokens),
            temperature=parameters.get("temperature", settings.temperature),
            model=parameters.get("model")
        )
        
        return {
            "llm_response": {
                "content": response.content,
                "tokens_used": response.tokens_used,
                "model": response.model,
                "cost": response.cost,
                "metadata": response.metadata
            }
        }
    
    async def _execute_financial_analyzer(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute financial analysis with LLM"""
        data = parameters.get("data")
        analysis_type = parameters.get("analysis_type", "general")
        
        # Подготовить промпт для анализа
        prompt = f"""
        Analyze the following financial data and provide insights:
        
        Data: {json.dumps(data, indent=2)}
        Analysis Type: {analysis_type}
        
        Provide:
        1. Revenue growth percentage
        2. Profit margin
        3. Cost reduction opportunities
        4. ROI calculation
        5. Key insights
        6. Recommendations
        """
        
        # Использовать LLM для анализа
        provider = self.llm_providers.get(settings.default_llm_provider)
        if provider:
            response = await provider.generate(prompt=prompt, max_tokens=2000)
            # Парсить ответ LLM в структурированный формат
            # (можно использовать JSON mode если поддерживается)
            analysis = self._parse_financial_analysis(response.content)
        else:
            # Fallback на симуляцию
            analysis = await self._simulate_financial_analysis(data)
        
        return analysis
```

**Оценка времени:** 3-4 часа  
**Зависимости:** LLM провайдеры должны быть готовы

---

## 🟠 ВЫСОКИЙ: Реальная меж-агентная коммуникация

### Проблема
- Агенты не общаются между собой
- Нет message bus

### Решение

#### Шаг 1: Создать Message Bus
**Файл:** `mcp_server/app/core/services/message_bus.py`

```python
from typing import Dict, List, Callable, Optional
import asyncio
import structlog
from agent_system.core.base_agent import AgentMessage

logger = structlog.get_logger()

class MessageBus:
    """Message bus for inter-agent communication"""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start message bus"""
        self._running = True
        self._processor_task = asyncio.create_task(self._process_messages())
        logger.info("Message bus started")
    
    async def stop(self):
        """Stop message bus"""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("Message bus stopped")
    
    def subscribe(self, agent_id: str, handler: Callable):
        """Subscribe agent to messages"""
        if agent_id not in self.subscribers:
            self.subscribers[agent_id] = []
        self.subscribers[agent_id].append(handler)
        logger.info("Agent subscribed", agent_id=agent_id)
    
    def unsubscribe(self, agent_id: str, handler: Callable):
        """Unsubscribe agent from messages"""
        if agent_id in self.subscribers:
            self.subscribers[agent_id].remove(handler)
    
    async def send(self, message: AgentMessage):
        """Send message through bus"""
        await self.message_queue.put(message)
        logger.debug(
            "Message queued",
            sender=message.sender_id,
            recipient=message.recipient_id,
            type=message.message_type.value
        )
    
    async def _process_messages(self):
        """Process messages from queue"""
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                
                # Отправить получателю
                recipient_id = message.recipient_id
                if recipient_id in self.subscribers:
                    for handler in self.subscribers[recipient_id]:
                        try:
                            await handler(message)
                        except Exception as e:
                            logger.error(
                                "Error in message handler",
                                recipient=recipient_id,
                                error=str(e)
                            )
                else:
                    logger.warning(
                        "No subscribers for message",
                        recipient=recipient_id
                    )
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Error processing message", error=str(e))

# Глобальный экземпляр
message_bus = MessageBus()
```

#### Шаг 2: Обновить BaseAgent для использования MessageBus
**Файл:** `agent_system/core/base_agent.py`

```python
from app.core.services.message_bus import message_bus

class BaseAgent(ABC):
    async def start(self):
        """Start the agent"""
        if self._running:
            return
        
        self._running = True
        
        # Подписаться на сообщения
        message_bus.subscribe(self.id, self.send_message)
        
        self._task_handler = asyncio.create_task(self._message_loop())
        logger.info("Agent started", agent_id=self.id)
    
    async def _send_message(self, message: AgentMessage):
        """Send message through the message bus"""
        await message_bus.send(message)
        logger.debug(
            "Message sent",
            agent_id=self.id,
            recipient_id=message.recipient_id,
            message_type=message.message_type.value
        )
```

**Оценка времени:** 2-3 часа  
**Зависимости:** Нет

---

## 🟡 СРЕДНИЙ: Исправление несоответствия схем БД

### Проблема
- Prisma использует SQLite
- Backend использует PostgreSQL
- Разные схемы

### Решение

#### Шаг 1: Обновить Prisma schema для PostgreSQL
**Файл:** `prisma/schema.prisma`

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

// Удалить старые модели User и Post, если они не нужны
// Или создать модели, соответствующие backend схеме
```

#### Шаг 2: Создать миграции Prisma
```bash
npx prisma migrate dev --name init
```

**Оценка времени:** 1-2 часа  
**Зависимости:** БД должна быть настроена

---

## 🟡 СРЕДНИЙ: Интеграция Frontend с Backend

### Проблема
- Frontend использует мок-данные
- Нет реальных API вызовов

### Решение

#### Шаг 1: Создать API клиент
**Файл:** `src/lib/api-client.ts`

```typescript
import axios from 'axios'

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Добавить interceptor для токена
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const api = {
  // Agents
  getAgents: () => apiClient.get('/api/v1/admin/agents'),
  getAgent: (id: string) => apiClient.get(`/api/v1/admin/agents/${id}`),
  
  // Tasks
  getTasks: (params?: any) => apiClient.get('/api/v1/resources/tasks', { params }),
  createTask: (data: any) => apiClient.post('/api/v1/resources/tasks', data),
  getTask: (id: string) => apiClient.get(`/api/v1/resources/tasks/${id}`),
  
  // Tools
  getTools: () => apiClient.get('/api/v1/tools'),
  executeTool: (data: any) => apiClient.post('/api/v1/tools/execute', data),
  
  // Health
  getHealth: () => apiClient.get('/api/v1/health'),
}
```

#### Шаг 2: Обновить page.tsx для использования API
**Файл:** `src/app/page.tsx`

```typescript
import { api } from '@/lib/api-client'
import { useQuery, useMutation } from '@tanstack/react-query'

export default function Home() {
  // Загрузить агентов
  const { data: agentsData } = useQuery({
    queryKey: ['agents'],
    queryFn: () => api.getAgents().then(res => res.data),
    refetchInterval: 5000, // Обновлять каждые 5 секунд
  })
  
  // Загрузить задачи
  const { data: tasksData } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.getTasks().then(res => res.data),
    refetchInterval: 3000,
  })
  
  // Загрузить статус сервера
  const { data: healthData } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.getHealth().then(res => res.data),
    refetchInterval: 10000,
  })
  
  // Использовать реальные данные вместо моков
  const agents = agentsData || []
  const tasks = tasksData || []
  const serverStatus = healthData || { status: 'offline' }
  
  // ... остальной код
}
```

**Оценка времени:** 3-4 часа  
**Зависимости:** Backend API должен быть готов

---

## 🟢 НИЗКИЙ: Система миграций БД

### Решение

#### Шаг 1: Настроить Alembic
**Файл:** `mcp_server/alembic.ini` (создать)

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://user:password@localhost/mcp_db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

#### Шаг 2: Создать первую миграцию
```bash
cd mcp_server
alembic init alembic
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

**Оценка времени:** 2-3 часа  
**Зависимости:** БД должна быть настроена

---

## Общий план выполнения

### Фаза 1: Критические исправления (1-2 недели)
1. ✅ Подключение к PostgreSQL
2. ✅ Подключение к Redis
3. ✅ Исправление безопасности
4. ✅ Реализация MCP протокола

### Фаза 2: Высокоприоритетные (1 неделя)
5. ✅ Исправление Agent Registry
6. ✅ Интеграция с LLM
7. ✅ Меж-агентная коммуникация

### Фаза 3: Средний приоритет (1 неделя)
8. ✅ Исправление схем БД
9. ✅ Интеграция Frontend-Backend

### Фаза 4: Низкий приоритет (по необходимости)
10. ✅ Система миграций

---

## Чеклист для каждого исправления

Для каждого пункта плана:
- [ ] Создать/обновить файлы
- [ ] Написать тесты
- [ ] Обновить документацию
- [ ] Проверить интеграцию
- [ ] Обновить docker-compose если нужно
- [ ] Проверить работу в production-like окружении

---

## Дополнительные рекомендации

1. **Тестирование**: Добавить unit и integration тесты для каждого компонента
2. **Логирование**: Улучшить структурированное логирование
3. **Мониторинг**: Настроить реальные метрики в Prometheus
4. **Документация**: Обновить API документацию
5. **CI/CD**: Настроить автоматическое тестирование и деплой

---

## Оценка общего времени

- Критические исправления: 14-18 часов
- Высокоприоритетные: 6-9 часов
- Средний приоритет: 4-6 часов
- Низкий приоритет: 2-3 часа

**Итого: 26-36 часов работы** (примерно 1 месяц при частичной занятости)

