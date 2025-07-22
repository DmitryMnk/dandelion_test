import datetime
from typing import Any, Dict

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ABCModel(AsyncAttrs, DeclarativeBase):
    """Абстрактная базовая модель для всех SQLAlchemy моделей в приложении.

    Наследует AsyncAttrs для поддержки асинхронного доступа к атрибутам и
    DeclarativeBase для определения моделей SQLAlchemy.

    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует модель в словарь.

        :return: Словарь, содержащий все поля модели и их значения.
        """
        return {
            field.name: getattr(self, field.name) for field in self.__table__.columns
        }

    def __repr__(self) -> str:
        """Создает строковое представление объекта модели.

        :return: Строка в формате "ИмяКласса(поле1 = значение1,
         поле2 = значение2, ...)".
        """
        attrs = ", ".join(f"{key} = {value}" for key, value in self.to_dict().items())
        return f"{self.__class__.__name__}({attrs})"


class ABCAdminModel(ABCModel):
    """Расширенная абстрактная модель с полями для
    отслеживания времени создания и обновления.
    Наследует ABCModel и добавляет поля для аудита изменений.
    """

    __abstract__ = True

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False),
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
