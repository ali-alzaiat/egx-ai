"""EGX-specific ingestion: universe discovery and provider assembly."""

from app.ingestion.egx.provider import EGXMarketDataProvider, create_egx_provider
from app.ingestion.egx.universe import (
    CompositeUniverseSource,
    PublicListingUniverseSource,
    SnapshotFileUniverseSource,
    UniverseEntry,
    UniverseSnapshot,
    UniverseSource,
    create_universe_source,
)

__all__ = [
    "EGXMarketDataProvider",
    "CompositeUniverseSource",
    "PublicListingUniverseSource",
    "SnapshotFileUniverseSource",
    "UniverseEntry",
    "UniverseSnapshot",
    "UniverseSource",
    "create_egx_provider",
    "create_universe_source",
]
