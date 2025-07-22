from contextlib import asynccontextmanager

from core.config import RedisSettings
from core.database.redis.connection import RedisConnectionManager
from services.redis import RedisManager


@asynccontextmanager
async def cache_manager():
    redis_settings = RedisSettings(HOST="localhost")
    connection_manager = RedisConnectionManager(redis_settings)
    pool = await connection_manager.get_redis_connection_pool(db=15)
    manager = RedisManager(pool)

    yield manager
    await pool.flushdb()
    await pool.aclose()
