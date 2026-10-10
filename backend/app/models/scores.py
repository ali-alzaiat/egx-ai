"""Database models for investment-score profiles and snapshots."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IndustryScoreProfile(Base):
    """Versioned per-industry score profile: which health track to run.

    ``sub_industry_id`` and ``egx_sector_id`` scope the profile; both NULL
    means the default profile used as fallback. Pattern mirrors
    ``IndustryValuationProfile`` (Phase 3) over the Phase-2 GICS taxonomy;
    the table name avoids any clash with ``industry_metric_profiles``.
    """

    __tablename__ = "industry_score_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_key: Mapped[str] = mapped_column(String(50), nullable=False)
    sub_industry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gics_sub_industries.id", ondelete="SET NULL"),
        nullable=True,
    )
    egx_sector_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("egx_sectors.id", ondelete="SET NULL"), nullable=True
    )
    health_track: Mapped[str] = mapped_column(String(20), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "profile_key", "methodology_version",
            name="uq_industry_score_profile",
        ),
        Index("ix_industry_score_profiles_profile_key", "profile_key"),
        Index("ix_industry_score_profiles_egx_sector_id", "egx_sector_id"),
        Index("ix_industry_score_profiles_sub_industry_id", "sub_industry_id"),
    )


class InvestmentScore(Base):
    """Persisted investment-score snapshot for one company."""

    __tablename__ = "investment_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    profile_key: Mapped[str] = mapped_column(String(50), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)
    headline: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    headline_status: Mapped[str] = mapped_column(String(20), nullable=False)
    components: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    checks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    confidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    buy_zone: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    n_with_data: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    margin_of_safety: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    inputs_echo: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "methodology_version",
            name="uq_investment_score",
        ),
        Index("ix_investment_scores_company_id", "company_id"),
    )
