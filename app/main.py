from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import FastAPI, status
from starlette.responses import JSONResponse

from core import settings
from services import startup_app
from services.middlewares import setup_middlewares

if TYPE_CHECKING:
    from fastapi import Request


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Управляет жизненным циклом приложения FastAPI.

    Эта асинхронная контекстная функция используется для выполнения
    операций при запуске и завершении работы приложения.

    :param app: Экземпляр приложения FastAPI, для которого
        управляется жизненный цикл.
    """
    startup_app(app)
    yield


app = FastAPI(
    docs_url=settings.API_PREFIX + "/docs",
    redoc_url=settings.API_PREFIX + "/redoc",
    openapi_url=settings.API_PREFIX + "/openapi.json",
    lifespan=lifespan,
)

setup_middlewares(app)


@app.exception_handler(Exception)  # type: ignore
async def general_exception_handler(
    request: "Request",
    exc: Exception,
) -> JSONResponse:
    """Обработчик исключений для обработки всех непредвиденных ошибок.

    Этот обработчик перехватывает все исключения, возникающие в приложении,
    и возвращает стандартный ответ с кодом состояния 400 и сообщением об ошибке.

    :param request: Объект запроса, который вызвал исключение.
    :param exc: Исключение, которое было вызвано.
    :return: Ответ в формате JSON с кодом состояния 400 и сообщением
        о том, что произошла ошибка.
    """
    response: JSONResponse = JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Что-то пошло не так.",
        },
    )
    return response
