from typing import TYPE_CHECKING

from api import setup_routers

if TYPE_CHECKING:
    from fastapi import FastAPI


def startup_app(app: "FastAPI") -> None:
    """Функция предназначена для утановки всех настроек приложения
    перед его стартом.
    """
    setup_routers(app)
