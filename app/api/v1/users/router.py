from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends

from api.v1.users.handlers import get_users_stats_v1_handler
from core.database.postgresql import psql_connection_manager
from infrastructure.schemas.api.users import GetUsersStatsV1DTO

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/users",
    tags=["Пользователи (v1)"],
)


@router.get(
    "/stats/{user_id}",
    description="Информация о пользователе.",
    response_model=GetUsersStatsV1DTO,
)
async def get_user_stats_v1(
    user_id: Annotated[
        int,
        Path(),
    ],
    session: Annotated[
        "AsyncSession",
        Depends(psql_connection_manager.session_dependency),
    ],
) -> GetUsersStatsV1DTO:
    """Запрос основных параметров пользователя.

    :param user_id: id пользователя.
    :param session: AsyncSession
    :return: GetUsersStatsV1DTO
    """
    return await get_users_stats_v1_handler(user_id, session)
