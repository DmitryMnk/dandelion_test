from typing import List

from ...abc import ABCSchema


class GetUsersStatsV1DTO(ABCSchema):
    """DTO GET /v1/users/stats."""

    events: List[str]
    score: int
    achievements: List[str]
