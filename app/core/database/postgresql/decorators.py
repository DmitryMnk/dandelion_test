from functools import wraps
from typing import Awaitable, Callable, ParamSpec, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from .connection import psql_connection_manager

T = TypeVar("T")
P = ParamSpec("P")


def session_decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """Декоратор, который автоматически предоставляет асинхронную
    SQLAlchemy сессию в декорируемую функцию.

    Если сессия уже присутствует в аргументах или именованных аргументах функции,
    то декоратор не создает новую сессию и вызывает функцию с существующими аргументами.
    В противном случае создается новая сессия и
    передается в функцию через параметр `session`.

    Декоратор также автоматически управляет транзакциями:
    - Начинает транзакцию перед вызовом функции
    - Фиксирует транзакцию, если функция выполнена успешно
    - Откатывает транзакцию в случае исключения
    - Закрывает сессию после завершения работы
    :param func: Декорируемая асинхронная функция, которая должна принимать
                    параметр `session` типа AsyncSession.
    :return: Декорированная функция, которая автоматически получает сессию БД.

    Пример использования:
        @session_decorator
        async def get_user(user_id: int, session: AsyncSession) -> User:
            return await session.get(User, user_id)
    """

    @wraps(func)
    async def decorated(*args: P.args, **kwargs: P.kwargs) -> T:
        is_session_in_args = any(isinstance(arg, AsyncSession) for arg in args)
        is_session_in_kwargs = any(
            isinstance(v, AsyncSession) for _, v in kwargs.items()
        )
        if is_session_in_args or is_session_in_kwargs:
            return await func(*args, **kwargs)

        session_maker = psql_connection_manager.get_session_maker()
        async with session_maker() as session:
            try:
                kwargs["session"] = session
                result = await func(
                    *args,
                    **kwargs,
                )
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise

    return decorated
