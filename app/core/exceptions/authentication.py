from core import settings


class InvalidTokenTypeException(Exception):
    """Исключение - не верный тип токена."""

    def __init__(
        self,
        message: str = settings.AUTH.INVALID_TOKEN_TYPE_MSG,
    ):
        """Инициализация исключения InvalidTokenTypeException.

        :param message: Сообщение об ошибке, которое будет отображаться.
            По умолчанию используется значение из настроек
            `settings.AUTH.INVALID_TOKEN_TYPE_MSG`.
        """
        self.message = message
        super().__init__(self.message)
