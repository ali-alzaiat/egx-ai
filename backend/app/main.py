from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security import require_api_token


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.API_DOCS_ENABLED else None,
        redoc_url="/redoc" if settings.API_DOCS_ENABLED else None,
        openapi_url="/openapi.json" if settings.API_DOCS_ENABLED else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    from app.api.ai import router as ai_router
    from app.api.alerts import router as alerts_router
    from app.api.companies import router as companies_router
    from app.api.data_quality import router as data_quality_router
    from app.api.data_sources import router as data_sources_router
    from app.api.disclosures import router as disclosures_router
    from app.api.events import router as events_router
    from app.api.financial import router as financial_router
    from app.api.health import router as health_router
    from app.api.industry import router as industry_router
    from app.api.ingestion import router as ingestion_router
    from app.api.metrics import router as metrics_router
    from app.api.scores import router as scores_router
    from app.api.screening import router as screening_router
    from app.api.signals import router as signals_router
    from app.api.stance import router as stance_router
    from app.api.statements import router as statements_router
    from app.api.technical import router as technical_router
    from app.api.theses import router as theses_router
    from app.api.triggers import router as triggers_router
    from app.api.valuation import router as valuation_router
    from app.api.watchlists import router as watchlists_router

    app.include_router(health_router)

    protected = [Depends(require_api_token)]
    app.include_router(statements_router, dependencies=protected)
    app.include_router(ai_router, dependencies=protected)
    app.include_router(alerts_router, dependencies=protected)
    app.include_router(companies_router, dependencies=protected)
    app.include_router(data_quality_router, dependencies=protected)
    app.include_router(data_sources_router, dependencies=protected)
    app.include_router(disclosures_router, dependencies=protected)
    app.include_router(events_router, dependencies=protected)
    app.include_router(financial_router, dependencies=protected)
    app.include_router(industry_router, dependencies=protected)
    app.include_router(ingestion_router, dependencies=protected)
    app.include_router(metrics_router, dependencies=protected)
    app.include_router(scores_router, dependencies=protected)
    app.include_router(screening_router, dependencies=protected)
    app.include_router(signals_router, dependencies=protected)
    app.include_router(stance_router, dependencies=protected)
    app.include_router(technical_router, dependencies=protected)
    app.include_router(theses_router, dependencies=protected)
    app.include_router(triggers_router, dependencies=protected)
    app.include_router(valuation_router, dependencies=protected)
    app.include_router(watchlists_router, dependencies=protected)

    return app


app = create_app()
