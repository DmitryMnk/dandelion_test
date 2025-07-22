from logging import Formatter, Logger, StreamHandler, getLogger
from logging.handlers import TimedRotatingFileHandler
from typing import Type

from core import settings

from .formatters import CustomJSONFormatter


def get_logger(
    name: str = settings.LOGGING.LOGGER_NAME,
    level: int = settings.LOGGING.LEVEL,
    formatter: Type[Formatter] = CustomJSONFormatter,
    disable_stream: bool = settings.LOGGING.DISABLE_STREAM,
) -> Logger:
    """Создает и настраивает логгер с указанным именем, уровнем и форматтером.

    :param name: Имя логгера, которое будет использоваться для идентификации.
    :param level: Уровень логирования (например, logging.DEBUG, logging.INFO и т.д.).
    :param formatter: Функция, возвращающая экземпляр Formatter,
        который будет использоваться для форматирования логов.
    :param disable_stream: Флаг - отключение вывода логов в консоль.
    :return: Настроенный экземпляр Logger.
    """
    logger: Logger = getLogger(name)
    logger.setLevel(level)
    file_handler = TimedRotatingFileHandler(
        settings.LOGGING.log_path + "/logs.json",
        when="midnight",
        interval=settings.LOGGING.INTERVAL,
        backupCount=settings.LOGGING.BACKUP_COUNT,
        encoding=settings.LOGGING.ENCODING,
    )
    file_handler.setLevel(level=level)
    file_handler.setFormatter(formatter())

    if not disable_stream:
        stream_handler = StreamHandler()
        stream_handler.setLevel(level=level)
        stream_handler.setFormatter(formatter())
        logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

    return logger


def setup_loggers() -> None:
    """Функция устанавливает настройки логгирования приложения."""
    getLogger("uvicorn.access").disabled = True


logger = get_logger()
