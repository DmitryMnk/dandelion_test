from enum import Enum


class EventTypeEnum(Enum):
    """Enum событий."""

    LOGIN = "login"
    COMPLETE_LEVEL = "complete_level"
    FIND_SECRET = "find_secret"


class AchievementsEnum(Enum):
    """Enum достижений."""

    BEGINNER = "Новичок"
    RESEARCHER = "Исследователь"
    MASTER = "Мастер"
