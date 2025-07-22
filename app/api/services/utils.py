import time
from typing import TYPE_CHECKING, Dict, Optional

from sqlalchemy import text

from core import settings
from core.database.postgresql import session_decorator

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy import TextClause
    from sqlalchemy.ext.asyncio import AsyncSession


@session_decorator
async def check_postgresql_connection(
    session: "AsyncSession",
) -> Dict[str, Optional[str | float]]:
    """Функция проверяет состояние подключения к PostgreSQL.

    :param session: AsyncSession
    :return: Краткий отчет о состоянии подключения к бд.
    """
    error: Optional[str] = None
    status: str = settings.HEALTH_MSG

    start_time: float = time.perf_counter()
    raw: "TextClause" = text("SELECT 1")

    try:
        await session.execute(raw)
    except Exception as exc:
        status = settings.UNHEALTH_MSG
        error = str(exc)
    end_time = time.perf_counter()
    response_time = (end_time - start_time) * 1000
    return {
        "status": status,
        "response_time": response_time,
        "error": error,
    }


async def check_redis_connection(
    redis: "Redis",
) -> Dict[str, Optional[str | float]]:
    """Функция проверяет состояние подключения к Redis.

    :param redis: Redis
    :return: Краткий отчет о состоянии подключения к Redis.
    """
    error: Optional[str] = None
    status: str = settings.HEALTH_MSG

    start_time: float = time.perf_counter()
    try:
        await redis.ping()
    except Exception as exc:
        status = settings.UNHEALTH_MSG
        error = str(exc)
    end_time = time.perf_counter()
    response_time = (end_time - start_time) * 1000
    return {
        "status": status,
        "response_time": response_time,
        "error": error,
    }
