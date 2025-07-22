from typing import Any, Generic, List, Type, TypeVar

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.roles import ExpressionElementRole

from infrastructure.models import ABCModel
from infrastructure.schemas import ABCSchema

M = TypeVar("M", bound=ABCModel)
S = TypeVar("S", bound=ABCSchema)


class ABCRepository(Generic[M]):
    """Репозиторий для работы с моделями, наследующимися от ABCModel.

    Этот класс предоставляет базовую функциональность для работы с
    асинхронной сессией базы данных и обеспечивает проверку типов
    для аргументов конструктора.
    Аттрибут model необходимо переопределять на модель, с которой
    будет работать репозиторий.


    :param model: Модель, с которой будет работать репозиторий.
        Должна наследоваться от ABCModel.

    :raises TypeError: Eсли аргумент session не является экземпляром
        AsyncSession или если атрибут model не наследуется от ABCModel.
    """

    model: Type[M]

    def __init__(self, session: AsyncSession):
        """Инициализация репозитория.

        :param session: Асинхронная сессия для работы с базой данных.
        """
        if not isinstance(session, AsyncSession):
            raise TypeError("Аргумент session должен быть AsyncSession.")

        if not issubclass(self.model, ABCModel) or self.model is ABCModel:
            raise TypeError("Аттрибут model должен наследоваться от ABCModel.")

        self.session = session

    def create_model_from_schema(self, schema: S) -> M:
        """Создает экземпляр модели из схемы Pydantic.

        :param schema: Схема Pydantic, содержащая данные для создания модели.
        :return: Новый экземпляр модели, созданный на основе данных схемы.
        """
        new_model: M = self.model(**schema.model_dump())
        return new_model

    async def create(self, schema: S) -> M:
        """Создает и сохраняет новый экземпляр модели в базе данных.

        :param schema: Схема Pydantic, содержащая данные для создания модели.
        :return: Сохраненный экземпляр модели.
        """
        new_model: M = self.create_model_from_schema(schema)
        self.session.add(new_model)
        await self.session.flush()
        await self.session.refresh(new_model)
        return new_model

    async def create_all(self, schemas: List[S]) -> None:
        """Создает и сохраняет несколько экземпляров модели в базе данных.

        :param schemas: Список схем Pydantic, содержащих данные для создания моделей.
        :type schemas: List[S]
        :return: None
        """
        models = [self.create_model_from_schema(schema) for schema in schemas]
        self.session.add_all(models)

    async def delete(self, filters: List[ExpressionElementRole[Any] | Any]) -> None:
        """Удаляет записи из базы данных на основе заданных фильтров.

        :param filters: Список условий для фильтрации записей, которые нужно удалить.
        """
        stmt = delete(self.model).filter(*filters)
        await self.session.execute(stmt)
