import json
from typing import Any, Dict, Optional, Type, TypeVar

from redis.asyncio import Redis

from core import settings
from core.database.redis import redis_connection_manager
from infrastructure.schemas import ABCSchema
from services.loggs import logg_error_data, logger

S = TypeVar("S", bound=ABCSchema)


class RedisManager:
    """Менеджер операций с редис."""

    def __init__(self, connection: "Redis"):
        """Инициализация менеджера.

        :param connection: Подключение к редис.
        """
        self.connection = connection

    @staticmethod
    def create_key(user_id: int, add_key: str) -> str:
        """Функция создают ключ.

        :param user_id: id пользователя.
        :param add_key: дополнительный ключ.
        :return: сгенерированный ключ.
        """
        return f"user:{user_id}:{add_key}"

    async def update_scores(
        self,
        user_id: int,
        scores: int,
    ) -> None:
        """Функция обнрвляет количество очков пользователя
        на переданную величину.

        :param user_id: id пользователя.
        :param scores: число заработанных очков.
        :return: None
        """
        key = self.create_key(user_id, "scores")
        try:
            logger.debug(
                "Обновление количества очков пользователя: %s",
                user_id,
            )
            await self.connection.incrby(key, scores)
        except Exception as e:
            logger.error(
                msg="Ошибка обновления очков пользователя.",
                extra=logg_error_data(e),
            )
            raise e

    async def get_scores(self, user_id: int) -> int:
        """Извлекаем количество очков из Redis.

        :param user_id: id пользователя.
        :return: Количество очков пользователя или 0, если запись отсутствует.
        """
        key = self.create_key(user_id, "scores")
        scores = await self.connection.get(key)
        if scores:
            return int(scores)
        return 0

    async def get_cache(
        self,
        key: str,
        model: Type[S],
    ) -> Optional[Dict[str, Any]]:
        """Извлекает данные из кэша по заданному ключу.
        :param model: Модель ответа сервера.
        :param key: Ключ для извлечения данных из кэша.
        :return: Данные из кэша или None, если данные не найдены.
        """
        try:
            data = await self.connection.get(key)
            if data:
                logger.debug("Извлечены данные из кэш по ключу: %s", key)
                result: Dict[str, Any] = json.loads(data)
                return model(**result)
            else:
                logger.debug("Кэш пустой, ключ: %s", key)
                return None
        except Exception as e:
            logger.error(
                msg="Ошибка извлечения данных из кэш по ключу: " + key,
                extra=logg_error_data(
                    e,
                ),
            )
        return None

    async def set_cache(
        self,
        key: str,
        data: S,
        exp: Optional[int] = None,
    ) -> None:
        """Устанавливает данные в кэш по заданному ключу с указанным временем жизни.

        Этот метод проверяет, является ли переданный объект экземпляром модели,
        наследованной от ABCSchema. Если это так, данные сериализуются в JSON
        и сохраняются в Redis с указанным временем жизни. Если время = None
        не указано, кэш устанавливается навсегда.

        :param key: Ключ для записи данных в кэш. Этот ключ будет использоваться
            для последующего извлечения данных из кэша.
        :param data: Данные, которые необходимо сохранить в кэше. Должны быть
            экземпляром модели, наследованной от ABCSchema.
        :param exp: Время жизни кэша в секундах. Определяет, как долго данные
           будут храниться в кэше перед их удалением.
        :return: Метод не возвращает значения. Он выполняет запись в кэш и
              логирует результат.
        """
        try:
            if not isinstance(data, ABCSchema):
                raise TypeError(
                    "Объект для записи в кэш должен быть Pydantic "
                    "моделью, наследованной от ABCSchema."
                )

            value = data.model_dump_json()
            await self.connection.set(key, value, exp)
            logger.debug("Данные кэшированы по ключу: %s", key)
        except Exception as e:
            logger.error(
                "Ошибка записи в кэш по ключу: " + key,
                extra=logg_error_data(e),
            )


redis_connection = redis_connection_manager.get_redis_connection_pool(
    settings.REDIS.CACHE_API_DB
)
redis_manager = RedisManager(connection=redis_connection)
