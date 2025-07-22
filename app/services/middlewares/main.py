from typing import TYPE_CHECKING

from .requests import logging_middleware

if TYPE_CHECKING:
    from fastapi import FastAPI


def setup_middlewares(app: "FastAPI") -> None:
    """Функция устанавливает все middleware приложения.

    :param app: Экземпляр приложения FastAPI, для которого
        управляется жизненный цикл.
    """
    app.middleware("http")(logging_middleware)
