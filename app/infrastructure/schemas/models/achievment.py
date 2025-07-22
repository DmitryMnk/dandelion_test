from ..abc import ABCSchema


class AchievementCreateSchema(ABCSchema):
    """Схема создания записи модели Achievement."""

    user_id: int
    name: str
