from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Body, Depends

from api.v1.events.handlers import post_event_v1_handler
from core.database.postgresql.connection import psql_connection_manager
from infrastructure.schemas.api import SuccessResponseDTO
from infrastructure.schemas.api.events import PostEventV1Request

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(
    prefix="/events",
    tags=["События (v1)"],
)


@router.post(
    "/event",
    summary="Обработка события.",
    description="Метод обрабатывает событие пользователя.",
    response_model=SuccessResponseDTO,
)
async def post_event(
    data: Annotated[
        PostEventV1Request,
        Body(),
    ],
    session: Annotated[
        "AsyncSession",
        Depends(psql_connection_manager.session_dependency),
    ],
) -> SuccessResponseDTO:
    """Запрос на обработку события.

    :param data: GetEventV1Request
    :param session: AsyncSession
    :return:
    """
    return await post_event_v1_handler(
        data,
        session,
    )
