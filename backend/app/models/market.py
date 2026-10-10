import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
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


class CompanyStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELISTED = "DELISTED"
    UNKNOWN = "UNKNOWN"


class DataSourceType(enum.StrEnum):
    EGX = "EGX"
    FRA = "FRA"
    COMPANY = "COMPANY"
    DATA_PROVIDER = "DATA_PROVIDER"
    MANUAL = "MANUAL"
    SYNTHETIC = "SYNTHETIC"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EGP")
    shares_outstanding: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    free_float: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    listing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[CompanyStatus] = mapped_column(
        Enum(CompanyStatus, name="company_status", create_constraint=True),
        nullable=False,
        default=CompanyStatus.ACTIVE,
    )
    egx_sector_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("egx_sectors.id", ondelete="RESTRICT"), nullable=True
    )
    gics_sub_industry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gics_sub_industries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    daily_prices: Mapped[list["DailyPrice"]] = relationship(
        "DailyPrice", back_populates="company", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("ticker", name="uq_company_ticker"),
        Index("ix_companies_ticker", "ticker"),
        Index("ix_companies_isin", "isin"),
        Index("ix_companies_sector", "sector"),
        Index("ix_companies_status", "status"),
        Index("ix_companies_egx_sector_id", "egx_sector_id"),
        Index("ix_companies_gics_sub_industry_id", "gics_sub_industry_id"),
    )


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[DataSourceType] = mapped_column(
        Enum(DataSourceType, name="data_source_type", create_constraint=True),
        nullable=False,
    )
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("name", name="uq_data_source_name"),)


class DailyPrice(Base):
    __tablename__ = "daily_prices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    value_traded: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    trades: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship("Company", back_populates="daily_prices")
    source: Mapped["DataSource"] = relationship("DataSource")

    __table_args__ = (
        UniqueConstraint("company_id", "date", name="uq_daily_price_company_date"),
        Index("ix_daily_prices_company_id", "company_id"),
        Index("ix_daily_prices_date", "date"),
        Index("ix_daily_prices_company_date", "company_id", "date"),
    )
