# MVP План на неделю (40-50 часов)

## 🎯 Цель MVP
Система должна:
- ✅ Запускаться и работать стабильно
- ✅ Сохранять данные в БД (не терять при перезапуске)
- ✅ Выполнять базовые задачи через агентов
- ✅ Иметь работающий MCP протокол для tools/list и tools/call
- ✅ Иметь базовую безопасность

## ❌ Что НЕ входит в MVP (отложить)
- Полная интеграция с LLM (оставить симуляцию)
- Меж-агентная коммуникация через message bus
- Frontend интеграция (оставить моки)
- Система миграций (использовать init-db.sql)
- Все MCP методы (только tools/list и tools/call)
- Сложная оркестрация задач

---

## 📅 Распределение по дням

### День 1-2 (16 часов): Инфраструктура данных
**Цель:** Данные сохраняются в БД, не теряются при перезапуске

### День 3-4 (16 часов): Базовый функционал
**Цель:** Система может создавать задачи и выполнять инструменты

### День 5 (8 часов): Безопасность и MCP протокол
**Цель:** Базовая аутентификация и работающий MCP endpoint

### День 6-7 (8-10 часов): Тестирование и фиксы
**Цель:** Все работает стабильно, нет критических багов

---

## 🔴 КРИТИЧНО ДЛЯ MVP (День 1-2)

### Задача 1: Подключение к PostgreSQL (6 часов)

#### Что нужно:
1. Модуль подключения к БД
2. Минимальные модели (только для tasks и tools)
3. Обновить TaskOrchestrator для сохранения в БД

#### Файлы для создания/изменения:

**1. `mcp_server/app/core/database.py`** (НОВЫЙ)
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
import structlog

logger = structlog.get_logger()
Base = declarative_base()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncSession:
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
    """Инициализация - таблицы уже созданы через init-db.sql"""
    # Просто проверяем подключение
    async with engine.begin() as conn:
        await conn.execute("SELECT 1")
    logger.info("Database connection verified")

async def close_db():
    await engine.dispose()
    logger.info("Database connections closed")
```

**2. `mcp_server/app/core/models/db_models.py`** (НОВЫЙ - минимальные модели)
```python
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class TaskModel(Base):
    __tablename__ = "tasks"
    __table_args__ = {"schema": "agents"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    domain = Column(String(100), nullable=False)
    priority = Column(String(50), default='medium')
    status = Column(String(50), default='pending')
    agent_id = Column(UUID(as_uuid=True))
    input_data = Column(JSON, default={})
    output_data = Column(JSON)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

class ToolModel(Base):
    __tablename__ = "tools"
    __table_args__ = {"schema": "mcp"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    input_schema = Column(JSON, nullable=False, default={})
    status = Column(String(50), default='active')
    category = Column(String(100))
```

**3. Обновить `mcp_server/app/core/services/task_orchestrator.py`**
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.models.db_models import TaskModel
from app.core.models.mcp_protocol import BusinessTask, TaskRequest, TaskResponse
from datetime import datetime, timedelta

class TaskOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.agent_registry = AgentRegistry()
    
    async def create_task(self, request: TaskRequest) -> TaskResponse:
        # Создать в БД
        db_task = TaskModel(
            title=request.title,
            description=request.description,
            domain=request.domain,
            priority=request.priority,
            input_data=request.input_data,
            status="pending"
        )
        self.db.add(db_task)
        await self.db.flush()  # Получить ID
        
        # Найти агента (упрощенная логика)
        agent_id = await self._find_suitable_agent(db_task)
        
        if agent_id:
            db_task.agent_id = agent_id
            db_task.status = "processing"
            db_task.started_at = datetime.utcnow()
        
        await self.db.commit()
        
        return TaskResponse(
            task_id=str(db_task.id),
            status=db_task.status,
            agent_id=str(agent_id) if agent_id else None
        )
    
    async def get_task(self, task_id: str) -> Optional[BusinessTask]:
        result = await self.db.execute(
            select(TaskModel).where(TaskModel.id == task_id)
        )
        db_task = result.scalar_one_or_none()
        if not db_task:
            return None
        
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
    
    async def list_tasks(self, status: str = None, domain: str = None, limit: int = 50, offset: int = 0) -> List[BusinessTask]:
        query = select(TaskModel)
        
        if status:
            query = query.where(TaskModel.status == status)
        if domain:
            query = query.where(TaskModel.domain == domain)
        
        query = query.order_by(TaskModel.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        db_tasks = result.scalars().all()
        
        return [
            BusinessTask(
                id=str(t.id),
                title=t.title,
                description=t.description,
                domain=t.domain,
                priority=t.priority,
                status=t.status,
                agent_id=str(t.agent_id) if t.agent_id else None,
                input_data=t.input_data,
                output_data=t.output_data,
                created_at=t.created_at,
                started_at=t.started_at,
                completed_at=t.completed_at,
                error_message=t.error_message
            )
            for t in db_tasks
        ]
```

**4. Обновить `mcp_server/app/main.py`**
```python
from app.core.database import init_db, close_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MCP Business AI Server", version=settings.app_version)
    try:
        await init_db()
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise
    yield
    await close_db()
    logger.info("Shutting down MCP Business AI Server")
```

**5. Обновить `mcp_server/app/api/v1/resources.py`** (использовать dependency injection)
```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.services.task_orchestrator import TaskOrchestrator

@router.post("/tasks", response_model=TaskResponse)
async def create_task(
    request: TaskRequest,
    db: AsyncSession = Depends(get_db)
):
    orchestrator = TaskOrchestrator(db)
    return await orchestrator.create_task(request)

@router.get("/tasks/{task_id}", response_model=BusinessTask)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    orchestrator = TaskOrchestrator(db)
    task = await orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

**Время:** 6 часов

---

### Задача 2: Подключение к Redis для rate limiting (4 часа)

**1. `mcp_server/app/core/redis_client.py`** (НОВЫЙ - упрощенная версия)
```python
import redis.asyncio as redis
from app.config import settings
import structlog

logger = structlog.get_logger()

class RedisClient:
    def __init__(self):
        self.client: redis.Redis = None
    
    async def connect(self):
        try:
            self.client = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.error("Redis connection failed", error=str(e))
            raise
    
    async def disconnect(self):
        if self.client:
            await self.client.close()
    
    async def zadd(self, key: str, score: float, member: str):
        await self.client.zadd(key, {member: score})
    
    async def zremrangebyscore(self, key: str, min_score: float, max_score: float):
        await self.client.zremrangebyscore(key, min_score, max_score)
    
    async def zcard(self, key: str) -> int:
        return await self.client.zcard(key)
    
    async def expire(self, key: str, seconds: int):
        await self.client.expire(key, seconds)

redis_client = RedisClient()
```

**2. Обновить `mcp_server/app/middleware/rate_limiting.py`**
```python
from app.core.redis_client import redis_client
import time

class RateLimitingMiddleware:
    async def __call__(self, request: Request, call_next):
        client_id = self._get_client_id(request)
        
        if not await self._check_rate_limit(client_id):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        await self._record_request(client_id)
        return await call_next(request)
    
    async def _check_rate_limit(self, client_id: str) -> bool:
        now = time.time()
        window_start = now - settings.rate_limit_window
        key = f"rate_limit:{client_id}"
        
        try:
            await redis_client.zremrangebyscore(key, 0, window_start)
            count = await redis_client.zcard(key)
            return count < settings.rate_limit_requests
        except Exception as e:
            logger.error("Rate limit check failed", error=str(e))
            return True  # Fail open
    
    async def _record_request(self, client_id: str):
        now = time.time()
        key = f"rate_limit:{client_id}"
        try:
            await redis_client.zadd(key, now, str(now))
            await redis_client.expire(key, settings.rate_limit_window)
        except Exception as e:
            logger.error("Rate limit record failed", error=str(e))
```

**3. Обновить `mcp_server/app/main.py`**
```python
from app.core.redis_client import redis_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        await redis_client.connect()
        logger.info("Services initialized")
    except Exception as e:
        logger.error("Failed to initialize", error=str(e))
        raise
    yield
    await redis_client.disconnect()
    await close_db()
```

**Время:** 4 часа

---

### Задача 3: Обновить config.py для валидации (1 час)

**Обновить `mcp_server/app/config.py`**
```python
class Settings(BaseSettings):
    secret_key: str  # Обязательное поле
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.secret_key or self.secret_key == "your-secret-key-change-in-production":
            raise ValueError("SECRET_KEY must be set in .env file")
```

**Время:** 1 час

---

### Задача 4: Обновить health check (1 час)

**Обновить `mcp_server/app/api/v1/health.py`**
```python
from app.core.redis_client import redis_client
from app.core.database import engine

@router.get("/")
async def health_check():
    services = {}
    
    # Check Database
    try:
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        services["database"] = True
    except:
        services["database"] = False
    
    # Check Redis
    try:
        await redis_client.client.ping()
        services["redis"] = True
    except:
        services["redis"] = False
    
    status = "healthy" if all(services.values()) else "degraded"
    
    return {
        "status": status,
        "services": services,
        "timestamp": datetime.utcnow().isoformat()
    }
```

**Время:** 1 час

**ИТОГО День 1-2:** 12 часов

---

## 🟠 ВЫСОКИЙ ПРИОРИТЕТ (День 3-4)

### Задача 5: Реализовать MCP tools/list и tools/call (6 часов)

**1. Обновить `mcp_server/app/core/services/tool_registry.py`** (сохранять в БД)
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.models.db_models import ToolModel

class ToolRegistry:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_all_tools(self) -> Dict[str, MCPTool]:
        result = await self.db.execute(select(ToolModel))
        tools = result.scalars().all()
        
        return {
            tool.name: MCPTool(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                status=ToolStatus(tool.status),
                category=tool.category,
                tags=tool.tags or []
            )
            for tool in tools
        }
    
    async def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        result = await self.db.execute(
            select(ToolModel).where(ToolModel.name == tool_name)
        )
        tool = result.scalar_one_or_none()
        if not tool:
            return None
        
        return MCPTool(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
            status=ToolStatus(tool.status),
            category=tool.category,
            tags=tool.tags or []
        )
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any], agent_id: Optional[str] = None) -> ToolExecution:
        # Получить tool из БД
        tool = await self.get_tool(tool_name)
        if not tool:
            raise ToolExecutionException(tool_name, "Tool not found")
        
        # Выполнить (оставить симуляцию для MVP)
        start_time = time.time()
        try:
            result = await self._execute_tool_implementation(tool, parameters)
            execution_time = time.time() - start_time
            
            # Сохранить в БД (если есть таблица tool_executions)
            # Пока просто возвращаем
            
            return ToolExecution(
                tool_name=tool_name,
                agent_id=agent_id or "system",
                parameters=parameters,
                result=result,
                execution_time=execution_time
            )
        except Exception as e:
            return ToolExecution(
                tool_name=tool_name,
                agent_id=agent_id or "system",
                parameters=parameters,
                error=str(e),
                execution_time=time.time() - start_time
            )
```

**2. Обновить `mcp_server/app/main.py`** (MCP handlers)
```python
async def handle_tools_list(message: Dict[str, Any], correlation_id: str):
    from app.core.services.tool_registry import ToolRegistry
    from app.core.database import get_db
    
    async for db in get_db():
        tool_registry = ToolRegistry(db)
        tools = await tool_registry.get_all_tools()
        
        mcp_tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema
            }
            for tool in tools.values()
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {"tools": mcp_tools}
        }

async def handle_tools_call(message: Dict[str, Any], correlation_id: str):
    from app.core.services.tool_registry import ToolRegistry
    from app.core.database import get_db
    
    params = message.get("params", {})
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    if not tool_name:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {"code": -32602, "message": "Tool name required"}
        }
    
    async for db in get_db():
        tool_registry = ToolRegistry(db)
        try:
            execution = await tool_registry.execute_tool(tool_name, arguments)
            
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "content": [{"type": "text", "text": str(execution.result)}],
                    "isError": execution.error is not None
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {"code": -32603, "message": str(e)}
            }
```

**Время:** 6 часов

---

### Задача 6: Исправить Agent Registry (2 часа)

**Обновить `mcp_server/app/core/services/agent_registry.py`**
```python
async def create_agent(self, request: AgentRequest) -> Agent:
    async with self._lock:
        if request.type not in self.agent_types:
            raise ValueError(f"Unknown agent type: {request.type}")
        
        agent_id = str(uuid.uuid4())  # Генерировать ДО создания
        
        agent_class = self.agent_types[request.type]
        agent = agent_class(
            agent_id=agent_id,  # Передать ID
            name=request.name,
            agent_type=request.type,
            capabilities=request.capabilities,
            config=request.config
        )
        
        self.agents[agent.id] = agent
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

async def get_agent(self, agent_id: str) -> Optional[Agent]:
    async with self._lock:
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        
        current_task_id = str(agent.current_task.id) if agent.current_task else None  # Безопасно
        
        return Agent(
            id=agent.id,
            name=agent.name,
            type=agent.type,
            description="",
            capabilities=agent.capabilities,
            status=agent.status,
            current_task_id=current_task_id,
            tasks_completed=agent.tasks_completed,
            last_activity=agent.last_activity,
            config=agent.config
        )
```

**Время:** 2 часа

---

### Задача 7: Базовая безопасность API ключей (2 часа)

**1. Обновить `mcp_server/app/middleware/auth.py`**
```python
from passlib.context import CryptContext
import hashlib

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthMiddleware:
    async def _verify_api_key(self, api_key: str) -> bool:
        # Для MVP: проверка против переменной окружения
        # В production - проверка в БД
        valid_key = os.getenv("API_KEY")
        if not valid_key:
            # Если нет API_KEY в env, разрешить для разработки
            return True
        
        # Простое сравнение (для MVP)
        return api_key == valid_key
```

**2. Обновить `.env.example`**
```env
API_KEY=your-api-key-here
SECRET_KEY=your-secret-key-here
```

**Время:** 2 часа

**ИТОГО День 3-4:** 10 часов

---

## 🟡 СРЕДНИЙ ПРИОРИТЕТ (День 5)

### Задача 8: Тестирование и фиксы (8 часов)

1. Протестировать все endpoints
2. Проверить сохранение данных в БД
3. Проверить rate limiting
4. Исправить найденные баги
5. Обновить документацию

**Время:** 8 часов

---

## 📋 Чеклист выполнения

### День 1-2 (12 часов)
- [ ] Создать `database.py`
- [ ] Создать `db_models.py` (минимальные модели)
- [ ] Обновить `task_orchestrator.py` для БД
- [ ] Обновить `resources.py` для dependency injection
- [ ] Создать `redis_client.py`
- [ ] Обновить `rate_limiting.py` для Redis
- [ ] Обновить `main.py` для инициализации
- [ ] Обновить `config.py` для валидации
- [ ] Обновить `health.py` для реальных проверок

### День 3-4 (10 часов)
- [ ] Обновить `tool_registry.py` для работы с БД
- [ ] Реализовать `handle_tools_list` в `main.py`
- [ ] Реализовать `handle_tools_call` в `main.py`
- [ ] Исправить `agent_registry.py` (ID и current_task)
- [ ] Обновить `auth.py` для API ключей

### День 5 (8 часов)
- [ ] Тестирование всех endpoints
- [ ] Проверка сохранения данных
- [ ] Исправление багов
- [ ] Обновление документации

---

## 🚀 Быстрый старт

### 1. Создать .env
```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/mcp_db
REDIS_URL=redis://localhost:6379
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
API_KEY=mcp-api-key-12345
```

### 2. Запустить инфраструктуру
```bash
docker-compose up -d postgres redis
```

### 3. Установить зависимости
```bash
cd mcp_server
pip install -r requirements.txt
```

### 4. Запустить сервер
```bash
uvicorn app.main:app --reload
```

### 5. Проверить
```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/tools
```

---

## ⚠️ Важные замечания

1. **Для MVP оставляем симуляцию LLM** - реальная интеграция займет больше времени
2. **Frontend остается с моками** - интеграция не критична для MVP
3. **Используем init-db.sql** - миграции отложены
4. **Упрощенная аутентификация** - для production нужна БД с API ключами

---

## 📊 Итоговая оценка

- **День 1-2:** 12 часов
- **День 3-4:** 10 часов  
- **День 5:** 8 часов
- **Резерв:** 2 часа

**ИТОГО: 32 часа** (4 рабочих дня по 8 часов)

Это реалистично для недели работы!

