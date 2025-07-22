from logging import DEBUG

from .main import get_logger

logger = get_logger(
    "appLogger",
    DEBUG,
)

request_logger = get_logger(
    "requestLogger",
    DEBUG,
)
