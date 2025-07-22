from typing import TYPE_CHECKING

from core.database.postgresql import session_decorator
from infrastructure.repositories.postgresql.achievement import AchievementRepository
from infrastructure.schemas.models import AchievementCreateSchema
from services.loggs import logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@session_decorator
async def check_user_achievement(
    achievement: str,
    user_id: int,
    session: "AsyncSession",
) -> bool:
    """Функция проверяет у пользователя наличие достижения.
    Если достижения нет, то создается запись о наличии в бд.

    :param achievement: Название достижения.
    :param user_id: id пользователя.
    :param session: AsyncSession.
    :return: True - достижение есть; False - достижения нет.
    """
    logger.debug(
        "Проверка наличия достижения: %s у пользователя: %s",
        achievement,
        user_id,
    )
    is_exist = await AchievementRepository(session).check_existing(
        {
            "user_id": user_id,
            "name": achievement,
        }
    )

    if not is_exist:
        logger.debug(
            "Достижение %s отсутсвует у пользователя %s. Пользователь "
            "получает это достижение.",
            achievement,
            user_id,
        )
        create_schema = AchievementCreateSchema(
            name=achievement,
            user_id=user_id,
        )
        await AchievementRepository(session).create(create_schema)
        return False

    logger.debug(
        "У пользователя: %s уже есть достижение: %s",
        user_id,
        achievement,
    )
    return True
