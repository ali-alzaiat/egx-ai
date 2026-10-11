"""Database models for Shariah screening persistence."""

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
    is_compliant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
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
    # Filing date the verdict inputs came from (R32 B2); None with reason
    # when unknown — never synthesized from the computation date.
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    report_date_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    # Absent fact label(s) behind INSUFFICIENT_DATA (R32 B2); None otherwise.
    missing_input: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Cited filing behind the rule inputs, e.g. "ANNUAL_REPORT filing
    # 2024-03-15" (R32 B2); industry rule cites "company record".
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_date: Mapped[date | None] = mapped_column(Date, nullable=True)
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


class ScreeningPurificationEstimate(Base):
    """Dividend-method purification estimate in EGP (R32 B3/B4).

    The amount stays NULL with status INSUFFICIENT_DATA until a cited filing
    ratio exists — a missing ratio is never substituted with zero.
    """

    __tablename__ = "screening_purification_estimates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    methodology_version: Mapped[str] = mapped_column(String(50), nullable=False)
    doctrine: Mapped[str] = mapped_column(String(50), nullable=False)
    branch: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_egp: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    dividend_egp: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    ratio: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    ratio_provenance: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dps: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    dps_source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dps_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_input: Mapped[str | None] = mapped_column(String(255), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "methodology_version",
            name="uq_screening_purification_estimate",
        ),
        Index("ix_screening_purification_estimates_company_id", "company_id"),
    )


class ScreeningEgxMembership(Base):
    """Dated EGX33 membership catalyst record (R32 B5).

    Membership is shown side by side with our verdict and never overrides it.
    """

    __tablename__ = "screening_egx_memberships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    methodology_version: Mapped[str] = mapped_column(String(50), nullable=False)
    member: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Semi-annual review cycle, e.g. "2026-02" / "2026-08".
    review_cycle: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # EGX review PDF (or press) behind the record.
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "review_cycle",
            name="uq_screening_egx_membership",
        ),
        Index("ix_screening_egx_memberships_company_id", "company_id"),
    )
