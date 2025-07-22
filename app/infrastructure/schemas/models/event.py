from typing import Dict

from ...enums.postgres_enums import EventTypeEnum
from ..abc import ABCSchema


class EventCreateSchema(ABCSchema):
    """Схема создания модели Event."""

    user_id: int
    event_type: EventTypeEnum
    details: Dict[str, int]
