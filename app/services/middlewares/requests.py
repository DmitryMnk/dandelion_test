import time
import uuid
from typing import TYPE_CHECKING, Awaitable, Callable, Dict, Union

from fastapi import Response

from services.loggs import logg_error_data, logger

if TYPE_CHECKING:
    from fastapi import Request


async def logging_middleware(
    request: "Request",
    call_next: Callable[["Request"], Awaitable[Response]],
) -> Response:
    """Обрабатывает входящие HTTP-запросы.

    :param request: Входящий HTTP-запрос.
    :param call_next: Функция для передачи управления следующему
        обработчику в цепочке middleware.
    :return: Ответ от следующего обработчика.

    :raises:
        Exception: Перехватывает и логирует исключения, возникающие
                    во время обработки запроса.
    """
    request_id = str(uuid.uuid4())

    start_time = time.time()

    request_info: Dict[str, Union[None, str, int, float]] = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "query_params": str(request.query_params),
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent", ""),
    }

    logger.info("Начало обработки запроса.", extra=request_info)

    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        request_info.update(
            {
                "status_code": response.status_code,
                "process_time_ms": round(process_time * 1000, 2),
            }
        )
        logger.info(
            "Обработка запроса завершена.",
            extra=request_info,
        )

        response.headers["X-Request-ID"] = request_id
        return response

    except Exception as e:
        process_time = time.time() - start_time
        extra = logg_error_data(e)
        extra.update(
            {
                "process_time_ms": round(process_time * 1000, 2),
            }
        )
        logger.error(
            "Ошибка обработки запроса.",
            extra=extra,
        )
        raise
