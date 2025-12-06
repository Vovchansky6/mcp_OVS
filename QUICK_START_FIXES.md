# Быстрый старт: Первые критические исправления

Этот файл содержит минимальный набор изменений для запуска системы с реальными подключениями к БД и Redis.

## Шаг 1: Создать базовую структуру подключений

### 1.1 Создать database.py
```bash
mkdir -p mcp_server/app/core
touch mcp_server/app/core/database.py
```

Скопировать код из `FIXES_PLAN.md` раздел "Подключение к PostgreSQL" → Шаг 1

### 1.2 Создать redis_client.py
```bash
touch mcp_server/app/core/redis_client.py
```

Скопировать код из `FIXES_PLAN.md` раздел "Подключение к Redis" → Шаг 1

### 1.3 Обновить requirements.txt
Убедиться что есть:
```
sqlalchemy[asyncio]==2.0.23
asyncpg==0.29.0
redis==5.0.1
aioredis==2.0.1
```

## Шаг 2: Минимальные изменения в main.py

Добавить в начало `mcp_server/app/main.py`:

```python
from app.core.database import init_db, close_db, get_db
from app.core.redis_client import redis_client
```

Обновить функцию `lifespan`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MCP Business AI Server", version=settings.app_version)
    
    try:
        await init_db()
        await redis_client.connect()
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise
    
    yield
    
    await redis_client.disconnect()
    await close_db()
    logger.info("Shutting down MCP Business AI Server")
```

## Шаг 3: Обновить .env файл

Создать `.env` в корне проекта:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/mcp_db

# Redis
REDIS_URL=redis://localhost:6379

# Security (ОБЯЗАТЕЛЬНО изменить!)
SECRET_KEY=your-generated-secret-key-here

# API Keys
EVOLUTION_API_KEY=your_evolution_key
OPENAI_API_KEY=your_openai_key
```

## Шаг 4: Проверка работы

### Запустить БД и Redis:
```bash
docker-compose up -d postgres redis
```

### Проверить подключение:
```bash
# PostgreSQL
docker-compose exec postgres psql -U postgres -d mcp_db -c "SELECT 1;"

# Redis
docker-compose exec redis redis-cli ping
```

### Запустить сервер:
```bash
cd mcp_server
python -m uvicorn app.main:app --reload
```

## Шаг 5: Тестирование

### Проверить health endpoint:
```bash
curl http://localhost:8000/api/v1/health
```

Должен вернуть статус всех сервисов.

## Следующие шаги

После успешного выполнения этих шагов, перейти к:
1. Созданию моделей БД (из FIXES_PLAN.md)
2. Обновлению TaskOrchestrator для работы с БД
3. Обновлению RateLimitingMiddleware для Redis

## Возможные проблемы

### Ошибка подключения к БД
- Проверить что PostgreSQL запущен
- Проверить DATABASE_URL в .env
- Проверить что init-db.sql выполнен

### Ошибка подключения к Redis
- Проверить что Redis запущен
- Проверить REDIS_URL в .env
- Проверить сеть docker-compose

### Ошибка импорта модулей
- Убедиться что все зависимости установлены: `pip install -r requirements.txt`
- Проверить структуру директорий

