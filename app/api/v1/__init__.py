from fastapi import APIRouter

from .events.router import router as event_router
from .users.router import router as users_router

router = APIRouter(prefix="/v1")
router.include_router(event_router)
router.include_router(users_router)
