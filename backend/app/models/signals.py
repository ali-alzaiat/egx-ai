import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.market import Company


class SignalTierDB(enum.StrEnum):
    STRONGEST = "STRONGEST"
    STRONG = "STRONG"
    NEUTRAL = "NEUTRAL"
    WEAK = "WEAK"
    WEAKEST = "WEAKEST"


class SignalStatusDB(enum.StrEnum):
    """Why a company is or is not in the ranking."""

    SCORED = "SCORED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    NO_PRICE_DATA = "NO_PRICE_DATA"
    NOT_ACTIVE = "NOT_ACTIVE"


class MarketSignal(Base):
    """A company's cross-sectional score for one date under one model version.

    Scores are only comparable within the same ``model_version``; the version is
    stored on every row so a ranking can always be reproduced and explained.
    """

    __tablename__ = "market_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[SignalStatusDB] = mapped_column(
        Enum(SignalStatusDB, name="signal_status", create_constraint=True),
        nullable=False,
        default=SignalStatusDB.SCORED,
    )
    tier: Mapped[SignalTierDB | None] = mapped_column(
        Enum(SignalTierDB, name="signal_tier", create_constraint=True), nullable=True
    )
    score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    universe_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_coverage: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    observations: Mapped[int | None] = mapped_column(Integer, nullable=True)

    factors: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    percentiles: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    excluded_factors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        UniqueConstraint(
            "company_id", "as_of", "model_version", name="uq_market_signal_company_date_model"
        ),
        Index("ix_market_signals_as_of_model", "as_of", "model_version"),
        Index("ix_market_signals_company_id", "company_id"),
        Index("ix_market_signals_rank", "as_of", "rank"),
    )


class SignalRun(Base):
    """One execution of the scoring engine, for auditability and backtesting."""

    __tablename__ = "signal_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)

    universe_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scored_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unscorable_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage_ratio: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0")
    )
    config: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("as_of", "model_version", name="uq_signal_run_date_model"),
        Index("ix_signal_runs_model", "model_name", "model_version"),
    )


class UniverseCoverageSnapshot(Base):
    """How much of the universe could actually be analysed on a given date.

    A market-wide tool has to publish its blind spots; without this a ranking
    silently describes only the part of the market the data provider covers.
    """

    __tablename__ = "universe_coverage_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)

    universe_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    with_price_data: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analyzable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unscorable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

    universe_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    universe_source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unpriced_tickers: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_fallback_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_universe_coverage_as_of", "as_of"),)
