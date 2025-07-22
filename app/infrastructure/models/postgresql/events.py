import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .abc import ABCModel


class Event(ABCModel):
    """Модель Событий."""

    __tablename__ = "events"

    user_id: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        comment="id пользователя.",
    )
    event_type: Mapped[str] = mapped_column(
        String(length=32),
        nullable=False,
        comment="Тип события",
    )

    details: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False),
        default=func.now(),
        nullable=False,
    )
