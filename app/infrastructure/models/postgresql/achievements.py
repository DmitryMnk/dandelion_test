import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .abc import ABCModel


class Achievement(ABCModel):
    """Модель достижений."""

    __tablename__ = "achievements"

    user_id: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(length=32),
        nullable=False,
    )

    unlocked_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "name",
            name="uix_achievements_user_name",
        ),
    )
