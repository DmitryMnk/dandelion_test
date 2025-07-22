from typing import TYPE_CHECKING

from fastapi import APIRouter

from core import settings

from .services.router import router as services_router
from .v1 import router as v1_router

if TYPE_CHECKING:
    from fastapi import FastAPI


def setup_routers(app: "FastAPI") -> None:
    """Функция устанавливает все роутеры приложения.

    :param app: FastAPI приложение.
    :return: None.
    """
    main_router = APIRouter(prefix=settings.API_PREFIX)
    main_router.include_router(v1_router)
    main_router.include_router(services_router)

    app.include_router(main_router)
