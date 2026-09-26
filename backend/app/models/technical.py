"""Database models for technical indicators persistence."""

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


class IndicatorTypeDB(enum.StrEnum):
    """Technical indicator types for database storage."""
    SMA = "sma"
    EMA = "ema"
    RSI = "rsi"
    MACD = "macd"
    BOLLINGER = "bollinger"
    OBV = "obv"
    VWAP = "vwap"


class IndicatorStatusDB(enum.StrEnum):
    """Indicator status for database storage."""
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INVALID = "INVALID"


class TechnicalIndicator(Base):
    """Technical indicator value for a company."""

    __tablename__ = "technical_indicators"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    indicator_type: Mapped[IndicatorTypeDB] = mapped_column(
        Enum(IndicatorTypeDB, name="indicator_type", create_constraint=True),
        nullable=False,
    )
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    status: Mapped[IndicatorStatusDB] = mapped_column(
        Enum(IndicatorStatusDB, name="indicator_status", create_constraint=True),
        nullable=False,
    )
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
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
            "company_id", "indicator_type", "calculated_at",
            name="uq_technical_indicator",
        ),
        Index("ix_technical_indicators_company_id", "company_id"),
        Index("ix_technical_indicators_indicator_type", "indicator_type"),
    )
