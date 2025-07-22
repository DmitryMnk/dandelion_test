from typing import TYPE_CHECKING

from infrastructure.repositories.postgresql import EventRepository
from infrastructure.schemas.api import SuccessResponseDTO
from infrastructure.schemas.models import EventCreateSchema
from services.celery.tasks.events import process_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from infrastructure.schemas.api.events import PostEventV1Request


async def post_event_v1_handler(
    data: "PostEventV1Request",
    session: "AsyncSession",
) -> SuccessResponseDTO:
    """Функция обрабатывае POST /v1/events/event.

    :param data: PostEventV1Request
    :param session: AsyncSession
    :return: SuccessResponseDTO
    """
    event_schema = EventCreateSchema(
        user_id=data.user_id,
        event_type=data.event_type,
        details=data.details.model_dump(),
    )
    await EventRepository(session).create(event_schema)
    process_event.delay(data.event_type, data.user_id, data.details.level)

    return SuccessResponseDTO()
