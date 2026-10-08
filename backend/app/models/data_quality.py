"""Database model for per-company data-quality assessments."""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DataQualityStatusDB(enum.StrEnum):
    """Data-quality status for database storage."""

    OK = "OK"
    DEGRADED = "DEGRADED"
    POOR = "POOR"
    MISSING = "MISSING"


class DataQualityAssessment(Base):
    """Quality of one company's data in one scope as of one date."""

    __tablename__ = "data_quality_assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(50), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[DataQualityStatusDB] = mapped_column(
        Enum(DataQualityStatusDB, name="data_quality_status", create_constraint=True),
        nullable=False,
    )
    components: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    issues: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=True
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "scope", "as_of", "methodology_version",
            name="uq_data_quality_assessment",
        ),
        Index(
            "ix_data_quality_assessment_company_scope",
            "company_id", "scope", text("as_of DESC"),
        ),
    )
