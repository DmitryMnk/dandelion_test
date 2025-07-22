import json
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Type,
    TypeVar,
)

from core import settings
from core.database.redis import redis_connection_manager
from infrastructure.schemas import ABCSchema
from services.loggs import logg_error_data, logger

if TYPE_CHECKING:
    from redis.asyncio import Redis


S = TypeVar("S", bound=ABCSchema)


class RedisCacheManager:
    """Менеджер кэширования с использованием Redis.

    Этот класс управляет кэшированием данных, используя Redis в качестве хранилища.
    Он предоставляет методы для получения и установки кэша, а также для генерации
    ключей кэша.
    Данный менеджер предназначен для кэширования функций, подготавливающих данные
    для ответа сервера (handlers).
    """

    def __init__(self, redis: "Redis"):
        """Инициализация RedisCacheManager.

        :param redis: Настройки подключения к Redis.
        """
        self.redis = redis

    @staticmethod
    def _create_cache_prefix_pattern(prefix: str) -> str:
        """Метод генерирует паттерн префикса для ключа.

        :param prefix: Префикс.
        :return: Метод возвращает строку - паттерн префикса в ключе для
            кэширования.
        """
        return f":{prefix}://"

    @staticmethod
    def _create_user_pattern(user_id: int | str) -> str:
        """Метод генерирует паттерн id пользователя для ключа.

        :param user_id: id пользователя.
        :return: Метод возвращает строку - паттерн id пользователя в ключе
            для кэширования.
        """
        return f"user:{user_id}:"

    def _generate_handler_key(
        self,
        prefix: str,
        func_name: str,
        additional_key: Optional[str],
        user_id: Optional[int | str],
    ) -> str:
        """Генерирует ключ для кэша на основе префикса, имени функции и
        дополнительного ключа.

        :param prefix: Префикс для ключа.
        :param func_name: Имя кэшированной функции.
        :param additional_key: Дополнительный ключ, для унификации по необходимости.
        :param user_id: id пользователя для унификации ключа при необходимости.
        :return: Сформированный ключ для кэша.
        """
        cache_prefix: str = self._create_cache_prefix_pattern(prefix)
        key: str = f"{cache_prefix}{func_name}:"
        if user_id:
            key += self._create_user_pattern(user_id)
        if additional_key:
            key += additional_key
        return key

    async def cache_handler(
        self,
        func: Callable[..., Awaitable[S]],
        dto_model: Type[S],
        *args: Any,
        expire: Optional[int] = None,
        prefix: str = "api",
        user_id: Optional[int | str] = None,
        additional_key: Optional[str] = None,
        **kwargs: Dict[str, Any],
    ) -> S:
        """Обрабатывает кэширование для заданной асинхронной функции.

        Проверяет наличие данных в кэше по сгенерированному ключу. Если данные найдены,
        они возвращаются. В противном случае вызывается функция, и результат кэшируется.

        :param func: Кэшируемая функция.
        :param dto_model: Модель DTO.
        :param args: Аргументы для функции.
        :param expire: Время жизни кэша в секундах (по умолчанию 60).
        :param prefix: Префикс для ключа кэша (по умолчанию "api").
        :param additional_key: Дополнительный ключ для кэша.
        :param user_id: id пользователя, для унификации ключа.
        :param kwargs: Дополнительные аргументы для функции.
        :return: Результат выполнения функции.
        """
        result: S
        cache_key: str = self._generate_handler_key(
            prefix,
            func.__name__,
            additional_key,
            user_id,
        )
        cache_data: Optional[Dict[str, Any]] = await self.get_cache(cache_key)
        if cache_data:
            result = dto_model(**cache_data)
            return result
        result = await func(*args, **kwargs)
        await self.set_cache(cache_key, result, expire)
        return result

    async def get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Извлекает данные из кэша по заданному ключу.
        :param key: Ключ для извлечения данных из кэша.
        :return: Данные из кэша или None, если данные не найдены.
        """
        try:
            data = await self.redis.get(key)
            if data:
                logger.debug("Извлечены данные из кэш по ключу: %s", key)
                result: Dict[str, Any] = json.loads(data)
                return result
            else:
                logger.debug("Кэш пустой, ключ: %s", key)
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
        exp: Optional[int],
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
            await self.redis.set(key, value, exp)
            logger.debug("Данные кэшированы по ключу: %s", key)
        except Exception as e:
            logger.error(
                "Ошибка записи в кэш по ключу: " + key,
                extra=logg_error_data(e),
            )

    async def invalidate_all(self) -> None:
        """Метод полностью очищает кэш.

        :return: Метод не возвращает значения.
        """
        logger.debug("Очищаем весь кэш.")
        try:
            await self.redis.flushdb()
            logger.debug("Проведена очистка кэша.")
        except Exception as e:
            logger.error(
                "Ошибка очистки кэша.",
                extra=logg_error_data(e),
            )

    async def invalidate_by_prefix(self, prefix: str) -> None:
        """Метод удаляет кэш по переданному префиксу.
        :param prefix: Префикс.
        :return: Метод не возвращает значения.
        """
        cache_prefix: str = self._create_cache_prefix_pattern(prefix)
        logger.debug(
            "Очищаем кэш по префиксу: %s",
            cache_prefix,
        )
        try:
            keys = await self.redis.keys(f"*{cache_prefix}*")
            if keys:
                await self.redis.delete(*keys)
                logger.debug(
                    "Проведена очистка кэша по профиксу: %s",
                    cache_prefix,
                )
            else:
                logger.debug(
                    "Кэш по префиксу пуст: %s",
                    prefix,
                )
        except Exception as e:
            logger.error(
                "Ошибка очистки кэша по префиксу: " + prefix,
                extra=logg_error_data(e),
            )

    async def invalidate_by_user(self, user_id: int | str) -> None:
        """Метод удаляет кеш по id пользователя.

        :param user_id: id пользователя.
        :return: Метод не возвращает значения.
        """
        user_cache_pattern: str = self._create_user_pattern(user_id)
        pattern: str = f"*:{user_cache_pattern}:*"

        logger.debug(
            "Очищаем кэш по id пользователя: %s",
            user_id,
        )

        try:
            keys: bytes = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(keys)
                logger.debug(
                    "Проведена очистка кэша по id пользователя: %s",
                    user_id,
                )
            else:
                logger.debug(
                    "Кэш по id пользователя пуст: %s",
                    user_id,
                )
        except Exception as e:
            logger.error(
                f"Ошибка очистки кэша по id пользователя: {user_id}",
                extra=logg_error_data(e),
            )


connection = redis_connection_manager.get_redis_connection_pool(
    settings.REDIS.CACHE_API_DB
)
redis_cache_manager = RedisCacheManager(connection)
