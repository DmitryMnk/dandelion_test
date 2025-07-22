from typing import TYPE_CHECKING

from redis.asyncio import ConnectionPool, Redis

from core.config import settings

if TYPE_CHECKING:
    from core.config import RedisSettings


class RedisConnectionManager:
    """Класс менеджер соединений с Redis.

    Этот класс управляет созданием и использованием соединений
    для работы с базой данных Redis.
    """

    def __init__(
        self,
        redis_settings: "RedisSettings",
    ):
        """Инициализирует экземпляр класса с настройками Redis.

        Этот конструктор принимает объект настроек Redis и сохраняет его
        для дальнейшего использования при создании пула соединений.

        :param redis_settings: Объект класса RedisSettings, содержащий
                               параметры подключения к Redis, такие как
                               хост, порт и пароль.
        """
        self.settings = redis_settings

    def _create_pool(self, db: int) -> ConnectionPool:
        """Создает пул соединений для указанной базы данных Redis.

        Этот метод использует настройки, сохраненные в экземпляре класса,
        для создания пула соединений, который будет использоваться для
        взаимодействия с Redis.

        :param db: Номер базы данных Redis, для которой создается пул соединений.
                   Это целое число, указывающее на конкретную базу данных
                   в экземпляре Redis. По умолчанию Redis использует 0.

        :return: Объект ConnectionPool, который управляет соединениями
                 с Redis для указанной базы данных.
        """
        return ConnectionPool(
            host=self.settings.HOST,
            port=self.settings.PORT,
            password=self.settings.PASSWORD,
            db=db,
        )

    def get_redis_connection_pool(self, db: int) -> Redis:
        """Получает подключение к пулу Redis для указанной базы данных.

        Этот метод создает пул соединений для Redis и возвращает объект Redis,
        который использует этот пул. Пул соединений позволяет эффективно управлять
        соединениями с Redis, минимизируя накладные расходы на их создание и
        уничтожение.

        :param db: Номер базы данных Redis, к которой нужно подключиться.
                    Это целое число, указывающее на конкретную базу данных
                    в экземпляре Redis. По умолчанию Redis использует 0.

        :return: Объект Redis, связанный с созданным пулом соединений.
                 Этот объект можно использовать для выполнения операций
                 с Redis, таких как чтение и запись данных.

        :raises ConnectionError: Если не удалось установить соединение с Redis.
        :raises ValueError: Если номер базы данных не является допустимым целым числом.
        """
        pool = self._create_pool(db)
        redis: Redis = Redis(connection_pool=pool)
        return redis


redis_connection_manager = RedisConnectionManager(settings.REDIS)
