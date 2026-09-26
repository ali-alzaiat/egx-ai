from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.market import DataSource

router = APIRouter(tags=["data-sources"])


@router.get("/api/data-sources")
async def list_data_sources(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List all data sources so the frontend can resolve source_id to source_type."""
    result = await session.execute(select(DataSource).order_by(DataSource.name))
    sources = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "source_type": s.source_type.value,
            "base_url": s.base_url,
            "description": s.description,
        }
        for s in sources
    ]
