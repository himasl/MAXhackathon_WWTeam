from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.auth import router as auth_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.public import router as public_router
from app.api.v1.routes import router as routes_router
from app.api.v1.users import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(routes_router)
router.include_router(catalog_router)
router.include_router(public_router)
router.include_router(admin_router)
router.include_router(assistant_router)
