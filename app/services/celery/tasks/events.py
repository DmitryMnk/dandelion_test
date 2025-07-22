import asyncio

from infrastructure.enums.postgres_enums import AchievementsEnum, EventTypeEnum
from services.redis.manager import redis_manager

from ...loggs import logger
from ..app import celery_app
from .utils import check_user_achievement


@celery_app.task
def send_achievement_notification(
    achievement: str,
    user_id: int,
) -> None:
    """Имитация отправки сообщения пользователю.

    :param achievement: Название достижения.
    :param user_id: id пользователя.
    :return: None
    """
    logger.info(
        "[Achievement] User: %s unlocked '%s'",
        user_id,
        achievement,
    )


@celery_app.task(serializer="json")
def process_event(
    event_type: str,
    user_id: int,
    level: int,
) -> None:
    """Функция обрабатывает событие.


    :param event_type: Тип события.
    :param user_id: id пользователя.
    :param level: уровень пользователя.
    :return: None
    """
    loop = asyncio.get_event_loop()
    scores = 0
    achievement = None
    match event_type:
        case EventTypeEnum.LOGIN.value:
            scores = 5
            achievement = AchievementsEnum.BEGINNER.value
        case EventTypeEnum.FIND_SECRET.value:
            scores = 50
            achievement = AchievementsEnum.RESEARCHER.value
        case EventTypeEnum.COMPLETE_LEVEL.value:
            scores = 20 + level
            achievement = AchievementsEnum.MASTER.value
    if scores > 0:
        loop.run_until_complete(
            redis_manager.update_scores(
                user_id,
                scores,
            ),
        )

    if achievement:
        is_exist_achievements = loop.run_until_complete(
            check_user_achievement(achievement, user_id)
        )

        if not is_exist_achievements:
            send_achievement_notification(achievement, user_id)
