"""Database models for valuation persistence."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
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
