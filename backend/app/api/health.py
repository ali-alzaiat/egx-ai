from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.APP_VERSION}


@router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION}
