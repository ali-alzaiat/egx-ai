from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.ai import router as ai_router
    from app.api.companies import router as companies_router
    from app.api.data_quality import router as data_quality_router
    from app.api.data_sources import router as data_sources_router
    from app.api.financial import router as financial_router
    from app.api.health import router as health_router
    from app.api.industry import router as industry_router
    from app.api.ingestion import router as ingestion_router
    from app.api.metrics import router as metrics_router
    from app.api.scores import router as scores_router
    from app.api.screening import router as screening_router
    from app.api.signals import router as signals_router
    from app.api.technical import router as technical_router
    from app.api.theses import router as theses_router
    from app.api.valuation import router as valuation_router

    app.include_router(health_router)
    app.include_router(ai_router)
    app.include_router(companies_router)
    app.include_router(data_quality_router)
    app.include_router(data_sources_router)
    app.include_router(financial_router)
    app.include_router(industry_router)
    app.include_router(ingestion_router)
    app.include_router(metrics_router)
    app.include_router(screening_router)
    app.include_router(scores_router)
    app.include_router(signals_router)
    app.include_router(technical_router)
    app.include_router(theses_router)
    app.include_router(valuation_router)

    return app


app = create_app()
