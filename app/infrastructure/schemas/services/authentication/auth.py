from typing import Optional

from pydantic import Field

from ...abc import ABCSchema


class PayloadSchema(ABCSchema):
    """Схема для вшитых данных токена."""

    id: str = Field(
        ...,
        description="id пользователя",
    )


class AuthorizedSchema(ABCSchema):
    """Схема авторизации пользователя."""

    is_auth: bool = Field(
        ...,
        description="Статус аутентификации пользователя",
    )

    payload: Optional[PayloadSchema] = Field(
        None,
        description="Нагрузка токена",
    )
