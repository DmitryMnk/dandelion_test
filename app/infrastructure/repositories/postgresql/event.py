from typing import List

from sqlalchemy import Result, select

from infrastructure.models.postgresql import Event

from .abc import ABCRepository


class EventRepository(ABCRepository[Event]):
    """Репозиторий модели Event."""

    model = Event

    async def get_last_events(self, user_id: int) -> List[str]:
        """Метод возвращает последние пять событиый пользователя.

        :param user_id: id пользователя.
        :return: Массив записей.
        """
        query = (
            select(self.model.event_type)
            .filter(
                self.model.user_id == user_id,
            )
            .order_by(self.model.created_at.desc())
            .limit(5)
        )

        result: Result = await self.session.execute(query)
        return list(result.scalars().all())
