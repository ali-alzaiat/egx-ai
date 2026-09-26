"""Database models for financial metric persistence."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.financial import FinancialFact, FinancialPeriod
    from app.models.market import Company


class MetricStatusDB(enum.StrEnum):
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INVALID = "INVALID"


class FinancialMetric(Base):
    """Calculated financial metric for a company and period."""

    __tablename__ = "financial_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_periods.id", ondelete="CASCADE"), nullable=False
    )
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[MetricStatusDB] = mapped_column(
        Enum(MetricStatusDB, name="metric_status", create_constraint=True),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    formula_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship("Company")
    period: Mapped["FinancialPeriod"] = relationship("FinancialPeriod")
    inputs: Mapped[list["FinancialMetricInput"]] = relationship(
        "FinancialMetricInput", back_populates="metric", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "period_id", "metric_code", "formula_version",
            name="uq_financial_metric",
        ),
        Index("ix_financial_metrics_company_id", "company_id"),
        Index("ix_financial_metrics_period_id", "period_id"),
        Index("ix_financial_metrics_metric_code", "metric_code"),
        Index("ix_financial_metrics_status", "status"),
    )


class FinancialMetricInput(Base):
    """Input fact used to calculate a financial metric (provenance)."""

    __tablename__ = "financial_metric_inputs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_metrics.id", ondelete="CASCADE"), nullable=False
    )
    fact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_facts.id", ondelete="CASCADE"), nullable=False
    )
    input_role: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    metric: Mapped["FinancialMetric"] = relationship("FinancialMetric", back_populates="inputs")
    fact: Mapped["FinancialFact"] = relationship("FinancialFact")

    __table_args__ = (
        UniqueConstraint(
            "metric_id", "fact_id", "input_role",
            name="uq_financial_metric_input",
        ),
        Index("ix_financial_metric_inputs_metric_id", "metric_id"),
        Index("ix_financial_metric_inputs_fact_id", "fact_id"),
    )
