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
