from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import add_exception_handlers
from app.api.v1.router import router as api_v1_router
from app.core.config import settings

app = FastAPI(title="Маршрут API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_v1_router)
add_exception_handlers(app)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
