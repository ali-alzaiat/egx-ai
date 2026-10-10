"""Database models for valuation persistence."""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
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


class ValuationModelDB(enum.StrEnum):
    """Valuation models for database storage."""
    PE = "price_to_earnings"
    PB = "price_to_book"
    EV_EBITDA = "ev_to_ebitda"
    DCF = "discounted_cash_flow"


class ValuationStatusDB(enum.StrEnum):
    """Valuation status for database storage."""
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INVALID = "INVALID"


class ValuationResult(Base):
    """Valuation result for a company."""

    __tablename__ = "valuation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[ValuationModelDB] = mapped_column(
        Enum(ValuationModelDB, name="valuation_model", create_constraint=True),
        nullable=False,
    )
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    status: Mapped[ValuationStatusDB] = mapped_column(
        Enum(ValuationStatusDB, name="valuation_status", create_constraint=True),
        nullable=False,
    )
    assumptions: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        UniqueConstraint(
            "company_id", "model", "calculated_at",
            name="uq_valuation_result",
        ),
        Index("ix_valuation_results_company_id", "company_id"),
        Index("ix_valuation_results_model", "model"),
    )


class IndustryValuationProfile(Base):
    """Versioned per-industry valuation profile: which models, which multiple.

    ``sub_industry_id`` and ``egx_sector_id`` scope the profile; both NULL
    means the default profile used as fallback.
    """

    __tablename__ = "industry_valuation_profiles"

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
    primary_model: Mapped[str] = mapped_column(String(50), nullable=False)
    fallback_model: Mapped[str] = mapped_column(String(50), nullable=False)
    preferred_multiple: Mapped[str] = mapped_column(String(10), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "profile_key", "methodology_version",
            name="uq_industry_valuation_profile",
        ),
        Index("ix_industry_valuation_profiles_profile_key", "profile_key"),
        Index("ix_industry_valuation_profiles_egx_sector_id", "egx_sector_id"),
        Index(
            "ix_industry_valuation_profiles_sub_industry_id", "sub_industry_id"
        ),
    )


class ValuationFairValue(Base):
    """Persisted weighted-fair-value snapshot for one company."""

    __tablename__ = "valuation_fair_values"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    profile_key: Mapped[str] = mapped_column(String(50), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)
    fair_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    fair_value_status: Mapped[str] = mapped_column(String(20), nullable=False)
    legs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    weights: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    scenarios: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    sensitivity: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    confidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    verdict: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    inputs_echo: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    price_as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "methodology_version",
            name="uq_valuation_fair_value",
        ),
        Index("ix_valuation_fair_values_company_id", "company_id"),
    )
