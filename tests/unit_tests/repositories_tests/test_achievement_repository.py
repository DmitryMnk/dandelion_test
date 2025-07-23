import pytest
from sqlalchemy import select

from tests.fixtures.postgresql import async_session


@pytest.mark.asyncio
async def test_create(async_session):
    from infrastructure.models.postgresql import Achievement
    from infrastructure.repositories.postgresql import AchievementRepository
    from infrastructure.schemas.models import AchievementCreateSchema

    data = {
        "user_id": 123,
        "name": "test_name",
    }

    new_achievement = AchievementCreateSchema(**data)

    await AchievementRepository(async_session).create(new_achievement)
    created_achievement = await async_session.execute(
        select(Achievement).where(Achievement.user_id == new_achievement.user_id)
    )
    created_achievement = created_achievement.scalars().first()

    assert created_achievement is not None
    assert created_achievement.user_id == data["user_id"]
    assert created_achievement.name == data["name"]
