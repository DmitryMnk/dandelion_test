from typing import TYPE_CHECKING

from infrastructure.repositories.postgresql import EventRepository
from infrastructure.repositories.postgresql.achievement import AchievementRepository
from infrastructure.schemas.api.users import GetUsersStatsV1DTO
from services.redis import redis_manager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from services.redis import RedisManager


async def get_users_stats_v1_handler(
    user_id: int,
    session: "AsyncSession",
    redis: "RedisManager" = redis_manager,
) -> GetUsersStatsV1DTO:
    """Функция обрабатывает запрос /v1/users/stats.

    Извлекаются события, достижения и число очков пользователя.
    :param user_id: id пользователя.
    :param session: AsyncSession.
    :param redis: RedisManager
    :return:
    """
    events = await EventRepository(session).get_last_events(user_id)
    score = await redis.get_scores(user_id)
    achievements = await AchievementRepository(session).get_user_achievements(user_id)

    return GetUsersStatsV1DTO(
        events=events,
        score=score,
        achievements=achievements,
    )
