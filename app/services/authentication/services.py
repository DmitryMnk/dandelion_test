import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

import bcrypt
from jwt import (
    ExpiredSignatureError,
    InvalidSignatureError,
    InvalidTokenError,
    decode,
    encode,
)
from pydantic import ValidationError

from core.config import settings
from core.exceptions.authentication import (
    InvalidTokenTypeException,
)
from infrastructure.schemas.services.authentication import (
    AuthorizedSchema,
    PayloadSchema,
)
from services.loggs import logg_error_data, logger

if TYPE_CHECKING:
    from core.config import AuthSettings


class AuthManager:
    """Класс для управления аутентификацией пользователей, включая хэширование паролей,
    создание и валидацию токенов доступа и обновления.
    """

    def __init__(
        self,
        auth_settings: "AuthSettings",
    ):
        """Инициализирует AuthManager с заданными настройками аутентификации.

        :param auth_settings: Настройки аутентификации (AuthSettings).
        """
        self.settings = auth_settings

    @staticmethod
    def hash_password(password: str) -> str:
        """Метод хэширует пароль.

        :param password: Исходный пароль
        :return: Хэшированный пароль
        """
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode()

    @staticmethod
    def verify_password(
        user_password: str,
        hashed_password: str,
    ) -> bool:
        """Метод проверяет пароль введенный пользователь с хэшированным.

        :param user_password: Пароль введенный пользователем.
        :param hashed_password: Хэшированный пароль.
        :return: True - пароли совпадают, False - пароли не совпадают.
        """
        return bcrypt.checkpw(
            user_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    def _create_token(
        self,
        data: Dict[str, Any],
        default_expire: datetime.timedelta,
        expire: datetime.timedelta | None = None,
    ) -> str:
        """Метод создает токен доступа.

        :param data: Payload токена.
        :param default_expire: Срок по умолчанию.
        :param expire: Срок.
        :return: Токен доступа.
        """
        to_encode = data.copy()
        now_date = datetime.datetime.now()
        exp = now_date + expire if expire else now_date + default_expire
        to_encode.update({"exp": exp})
        return encode(
            to_encode,
            self.settings.PRIVATE_KEY,
            algorithm=self.settings.ALGORITHM,
        )

    def create_access_token(
        self,
        data: Dict[str, Any],
        expire_delta: datetime.timedelta | None = None,
    ) -> str:
        """Метод возвращает access токен доступа.

        :param data: Payload токена.
        :param expire_delta: Срок.
        :return: access токен доступа.
        """
        data.update({"token_type": self.settings.ACCESS_TOKEN_TYPE})
        default_exp = datetime.timedelta(
            minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        return self._create_token(data, default_expire=default_exp, expire=expire_delta)

    def create_refresh_token(
        self,
        data: Dict[str, Any],
        expire_delta: datetime.timedelta | None = None,
    ) -> str:
        """Метод возвращает refresh токен доступа.

        :param data: Payload токена.
        :param expire_delta: Срок.
        :return: access токен доступа.
        """
        data.update({"token_type": self.settings.REFRESH_TOKEN_TYPE})
        default_exp = datetime.timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS)
        return self._create_token(data, default_expire=default_exp, expire=expire_delta)

    def _decode_jwt(
        self,
        token: str,
    ) -> Dict[str, Any]:
        """Функция декодирует токен и возвращает нагрузку.

        Исключения, возникающие при декодировании не обрабатываются.
        Функция создана как обертка для разделения логики и удобства
        тестирования.
        :param token: Токен
        :return: Вшитые данные.
        """
        payload: Dict[str, Any] = decode(
            token,
            key=self.settings.PUBLIC_KEY,
            algorithms=[self.settings.ALGORITHM],
        )
        return payload

    @staticmethod
    def _create_auth_schema(
        payload: Dict[str, Any],
    ) -> PayloadSchema:
        """Функция создает схему PayloadSchema из данных вшитых в токен.

        :param payload: Вшитые данные в токен.
        :raises ValidationError: Ошибка при валидации токена.
        :return: PayloadSchema
        """
        return PayloadSchema(**payload)

    @staticmethod
    def _check_token_type(
        payload: PayloadSchema,
        token_type: str,
    ) -> None:
        """Функция проверяет тип токена.

        :param payload: PayloadSchema
        :param token_type: тип токена для проверки.
        :raises InvalidTokenTypeException: Исключение, которое возникает в случае
            неправильного типа токена.
        :return: None
        """
        if payload.token_type != token_type:
            raise InvalidTokenTypeException

    def get_payload_or_none(self, token: str) -> Optional[Dict[str, Any]]:
        """Декодирует токен и возвращает полезную нагрузку, если токен валиден.

        :param token: Токен для декодирования.
        :return: Полезная нагрузка токена, если токен валиден; иначе None.
        """
        try:
            payload: Dict[str, Any] = self._decode_jwt(token)
            if payload.get("exp"):
                del payload["exp"]
            return payload
        except ExpiredSignatureError:
            pass
        except InvalidSignatureError as exc:
            logger.error(
                msg="Подпись при валидации токена доступа не может быть проверена.",
                extra=logg_error_data(exc),
            )
        except InvalidTokenError as exc:
            logger.error(
                msg="Токен не может быть декодирован.",
                extra=logg_error_data(exc),
            )
        except Exception as exc:
            logger.error(
                msg="Ошибка при декодировании токена.",
                extra=logg_error_data(exc),
            )
        return None

    def get_auth_schema(
        self,
        token: str,
        token_type: str = settings.AUTH.ACCESS_TOKEN_TYPE,
    ) -> Optional[AuthorizedSchema]:
        """Получает схему авторизации на основе токена.

        :param token: Токен для проверки.
        :param token_type: Ожидаемый тип токена. По умолчанию используется
            значение из настроек AUTH.ACCESS_TOKEN_TYPE.
        :return: Схема авторизации, если токен валиден и тип токена совпадает;
            иначе None.
        """
        payload = self.get_payload_or_none(token)
        if not payload:
            return None
        else:
            try:
                auth_schema = self._create_auth_schema(payload)
            except ValidationError as exc:
                logger.error(
                    msg="Ошибка валидации данных токена.",
                    extra=logg_error_data(exc),
                )
                return None

            try:
                self._check_token_type(auth_schema, token_type)
            except InvalidTokenTypeException as exc:
                logger.error(
                    msg=exc.message,
                    extra=logg_error_data(exc),
                )
                return None
            return AuthorizedSchema(
                is_auth=True,
                payload=auth_schema,
            )


auth_manager = AuthManager(auth_settings=settings.AUTH)
