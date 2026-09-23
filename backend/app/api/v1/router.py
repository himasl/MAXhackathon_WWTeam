from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.routes import router as routes_router
from app.api.v1.users import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(routes_router)

