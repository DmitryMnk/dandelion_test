import datetime

import psutil
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.database.redis import redis_connection_manager

from .utils import check_postgresql_connection, check_redis_connection

router = APIRouter(prefix="/services", tags=["Сервис"])


@router.get("/health")
async def health_check() -> JSONResponse:
    """Метод проверяет состояние приложения и сервисов.

    :return: JSONResponse с кратким отчетом о состоянии
        приложения и сервисов.
    """
    data = {
        "status": "healthy",
        "timestamp": datetime.datetime.now().timestamp(),
        "services": {
            "postgresql": await check_postgresql_connection(),
            "redis": await check_redis_connection(
                redis_connection_manager.get_redis_connection_pool(1)
            ),
        },
    }

    response = JSONResponse(content=data)
    return response


@router.get("/metrics")
async def get_metrics() -> JSONResponse:
    """Метод возворащает метрики загрузки ресурсов.

    :return: JSONResponse c метриками нагрузки CPU, RAM и
    дискового пространства.
    """
    data = {
        "cpu_usage": psutil.cpu_percent(),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage("/").percent,
    }
    response = JSONResponse(content=data)
    return response
