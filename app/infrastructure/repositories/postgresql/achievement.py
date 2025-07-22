from typing import TYPE_CHECKING, List

from sqlalchemy import select

from infrastructure.models.postgresql import Achievement
from infrastructure.repositories.postgresql.abc import ABCRepository

if TYPE_CHECKING:
    from sqlalchemy import Result


class AchievementRepository(ABCRepository[Achievement]):
    """Репозиторий модели Achievement."""

    model = Achievement

    async def get_user_achievements(self, user_id: int) -> List[str]:
        """Метод извлекает все достижения пользователя.

        :param user_id: id пользователя.
        :return: Список записей.
        """
        query = select(self.model.name).filter(self.model.user_id == user_id)
        result: "Result" = await self.session.execute(query)

        return list(result.scalars().all())
