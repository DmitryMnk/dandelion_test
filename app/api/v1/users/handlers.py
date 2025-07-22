from typing import TYPE_CHECKING

from core import settings
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
    key = redis_manager.create_key(
        user_id=user_id,
        add_key="stats",
    )

    cache = await redis_manager.get_cache(key, GetUsersStatsV1DTO)
    if cache:
        return cache

    events = await EventRepository(session).get_last_events(user_id)
    score = await redis.get_scores(user_id)
    achievements = await AchievementRepository(session).get_user_achievements(user_id)
    response = GetUsersStatsV1DTO(
        events=events,
        score=score,
        achievements=achievements,
    )
    await redis_manager.set_cache(key, response, exp=settings.REDIS.CACHE_TTL_SEC)
    return response
