"""Database models for Shariah screening persistence."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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
    from app.models.market import Company


class ScreeningStatusDB(enum.StrEnum):
    """Screening status for database storage."""
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ShariahScreeningResult(Base):
    """Shariah screening result for a company."""

    __tablename__ = "shariah_screening_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    is_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[ScreeningStatusDB] = mapped_column(
        Enum(ScreeningStatusDB, name="screening_status", create_constraint=True),
        nullable=False,
    )
    methodology_version: Mapped[str] = mapped_column(String(50), nullable=False)
    methodology_name: Mapped[str] = mapped_column(String(255), nullable=False)
    overall_reason: Mapped[str] = mapped_column(Text, nullable=False)
    screened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship("Company")
    rule_results: Mapped[list["ScreeningRuleResultDB"]] = relationship(
        "ScreeningRuleResultDB", back_populates="screening_result", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "methodology_version",
            name="uq_shariah_screening_result",
        ),
        Index("ix_shariah_screening_results_company_id", "company_id"),
        Index("ix_shariah_screening_results_is_compliant", "is_compliant"),
        Index("ix_shariah_screening_results_methodology_version", "methodology_version"),
    )


class ScreeningRuleResultDB(Base):
    """Individual screening rule result for auditability."""

    __tablename__ = "screening_rule_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    screening_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shariah_screening_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    verdict: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    screening_result: Mapped["ShariahScreeningResult"] = relationship(
        "ShariahScreeningResult", back_populates="rule_results"
    )

    __table_args__ = (
        Index("ix_screening_rule_results_screening_result_id", "screening_result_id"),
        Index("ix_screening_rule_results_rule_name", "rule_name"),
    )
