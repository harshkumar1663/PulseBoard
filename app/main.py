from fastapi import FastAPI # type: ignore
import asyncio
from app.core.config import settings
from app.api import api_router
from app.db.session import engine, Base
import app.db.base  # noqa: F401 ensures models are imported

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


app.include_router(api_router, prefix="/api")


@app.on_event("startup")
async def on_startup():
    """Ensure database tables exist on startup.
    Alembic migrations are preferred in production; this is a safety net for local/test runs.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
