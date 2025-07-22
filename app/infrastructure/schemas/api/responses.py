from ..abc import ABCSchema


class SuccessResponseDTO(ABCSchema):
    """Стандартный успешный ответ сервера."""

    success: bool = True
