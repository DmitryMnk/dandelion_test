from pydantic import Field

from infrastructure.enums.postgres_enums import EventTypeEnum

from ...abc import ABCSchema


class GetEventV1Details(ABCSchema):
    """Вложенная модель details."""

    level: int = Field(..., gt=0)


class PostEventV1Request(ABCSchema):
    """Данные POST запроса /v1/events/event."""

    user_id: int
    event_type: EventTypeEnum
    details: GetEventV1Details
