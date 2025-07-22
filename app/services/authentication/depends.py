from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core import settings

from .services import auth_manager

if TYPE_CHECKING:
    from infrastructure.schemas.services.authentication import AuthorizedSchema

    from .services import AuthManager

http_bearer = HTTPBearer(
    scheme_name="Bearer",
    description="Set token to header (without Bearer in start).",
    auto_error=False,
)


def check_auth(
    token: str,
    manager: "AuthManager" = auth_manager,
) -> "AuthorizedSchema":
    """Проверка авторизации пользователя по токену.

    Эта функция получает схему авторизации на основе предоставленного токена.
    Если токен недействителен или пользователь не авторизован, будет вызвано
    исключение HTTPException с кодом 401.

    :param token: Токен доступа, предоставленный пользователем для проверки авторизации.
    :param manager: Менеджер аутентификации (AuthManager), используемый для
        проверки токена.
                    По умолчанию используется глобальный экземпляр auth_manager.
    :return: Схема авторизации (AuthorizedSchema), если токен действителен и
        пользователь авторизован.
    :raises HTTPException: Исключение, возникающее в случае, если токен недействителен
    или пользователь не авторизован.
    """
    auth_schema = manager.get_auth_schema(token)
    if not auth_schema:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=settings.AUTH.USER_NOT_AUTHENTICATED_MSG,
        )
    return auth_schema


def user_depends(
    credentials: Annotated[
        HTTPAuthorizationCredentials,
        Depends(http_bearer),
    ],
) -> "AuthorizedSchema":
    """Не строгая проверка авторизации пользователя.

    Если токен не передан - считаем, что пользователь не авторизован.
    Если токен передан - выполняем валидацию токена и вызываем исключение
        если валидация не пройдена.
    :param credentials: токен доступа.
    :return: Схема данных, содержащая информацию
    о пользователе, если токен действителен.
    """
    token = credentials.credentials
    if token:
        return check_auth(credentials.credentials)
    return check_auth(token)


def user_depends_strong(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer)],
) -> "AuthorizedSchema":
    """Cтрогая проверка авторизации пользователя.

    Если токен не передан - считаем, что пользователь не авторизован.
    Если токен передан - выполняем валидацию токена и вызываем исключение
        если валидация не пройдена.
    :param credentials: токен доступа.
    :return: Схема данных, содержащая информацию
    о пользователе, если токен действителен.
    """
    token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=settings.AUTH.TOKEN_NOT_FOUND_MSG,
        )
    return check_auth(token)
