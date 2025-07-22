from typing import TYPE_CHECKING, Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ...config import settings

if TYPE_CHECKING:
    from core.config import PostgresSettings


class PSQLConnectionManager:
    """Класс менеджер соединений с PostgreSQL.

    Этот класс управляет созданием и использованием асинхронных сессий
    для работы с базой данных PostgreSQL.
    Он использует SQLAlchemy для управления соединениями и сессиями.
    """

    def __init__(
        self,
        psql_settings: "PostgresSettings",
    ):
        """Класс менеджер соединений с PostgreSQL.

        Этот класс управляет созданием и использованием асинхронных сессий
        для работы с базой данных PostgreSQL. Он использует SQLAlchemy для
        управления соединениями и сессиями.
        :param psql_settings: Настройки подключения к базе данных PostgreSQL.
        """
        self.settings = psql_settings
        self.engine = create_async_engine(
            url=self.settings.get_connection_url(),
            pool_size=self.settings.POOL_SIZE,
            max_overflow=self.settings.MAX_OVERFLOW,
            pool_timeout=self.settings.POOL_TIMEOUT,
            pool_recycle=self.settings.POOL_RECYCLE,
            pool_pre_ping=self.settings.POOL_PRE_PING,
            echo=self.settings.ECHO,
        )
        self.session_maker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            autoflush=self.settings.AUTOFLUSH,
            autocommit=self.settings.AUTOCOMMIT,
            expire_on_commit=self.settings.EXPIRE_ON_COMMIT,
        )

    def get_session_maker(self) -> async_sessionmaker[AsyncSession]:
        """Возвращает объект async_sessionmaker.
        :return: Объект, используемый для создания асинхронных сессий.
        """
        session: async_sessionmaker[AsyncSession] = self.session_maker
        return session

    async def session_dependency(self) -> AsyncGenerator[AsyncSession, Any]:
        """Генератор асинхронной сессии.

        Этот метод создает асинхронную сессию, управляет ее жизненным циклом
        и обеспечивает автоматическую фиксацию или откат транзакции в случае ошибки.

        :yields: AsyncSession - Асинхронная сессия для работы с базой данных.
        :rises: Exception - Если происходит ошибка во время работы с сессией,
                транзакция будет откатана.
        :return:
        """
        async with self.session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


psql_connection_manager = PSQLConnectionManager(settings.POSTGRES)
