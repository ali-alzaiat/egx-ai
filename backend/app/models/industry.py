"""Database models for GICS taxonomy, EGX sector mapping, peers, and profiles."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GicsSector(Base):
    """GICS level 1: one of the 11 GICS sectors (canonical taxonomy)."""

    __tablename__ = "gics_sectors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(2), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("code", name="uq_gics_sector_code"),
        Index("ix_gics_sectors_code", "code"),
    )


class GicsIndustryGroup(Base):
    """GICS level 2: industry group within a sector."""

    __tablename__ = "gics_industry_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gics_sectors.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(4), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("code", name="uq_gics_industry_group_code"),
        Index("ix_gics_industry_groups_code", "code"),
        Index("ix_gics_industry_groups_sector_id", "sector_id"),
    )


class GicsIndustry(Base):
    """GICS level 3: industry within an industry group."""

    __tablename__ = "gics_industries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gics_industry_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("code", name="uq_gics_industry_code"),
        Index("ix_gics_industries_code", "code"),
        Index("ix_gics_industries_group_id", "group_id"),
    )


class GicsSubIndustry(Base):
    """GICS level 4: sub-industry within an industry (company classification)."""

    __tablename__ = "gics_sub_industries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    industry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gics_industries.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("code", name="uq_gics_sub_industry_code"),
        Index("ix_gics_sub_industries_code", "code"),
        Index("ix_gics_sub_industries_industry_id", "industry_id"),
    )


class EgxSector(Base):
    """One of the 18 EGX-native sectors (mapping layer, never the canonical key)."""

    __tablename__ = "egx_sectors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("name", name="uq_egx_sector_name"),
        Index("ix_egx_sectors_name", "name"),
    )


class EgxSectorGicsMap(Base):
    """EGX sector to GICS sub-industry mapping row, each with provenance."""

    __tablename__ = "egx_sector_gics_map"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    egx_sector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("egx_sectors.id", ondelete="CASCADE"), nullable=False
    )
    sub_industry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gics_sub_industries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "egx_sector_id", "sub_industry_id", name="uq_egx_sector_gics_map"
        ),
        Index("ix_egx_sector_gics_map_egx_sector_id", "egx_sector_id"),
        Index("ix_egx_sector_gics_map_sub_industry_id", "sub_industry_id"),
    )


class CompanyPeerOverride(Base):
    """Per-company editable peer list that wins over default peer resolution."""

    __tablename__ = "company_peer_overrides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    peer_company_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("company_id", name="uq_company_peer_override"),
        Index("ix_company_peer_overrides_company_id", "company_id"),
    )


class IndustryMetricProfile(Base):
    """One metric row of a versioned per-industry metric profile.

    ``sub_industry_id`` and ``egx_sector_id`` scope the profile; both NULL
    means the default profile used as fallback.
    """

    __tablename__ = "industry_metric_profiles"

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
    metric_key: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "profile_key", "metric_key", "methodology_version",
            name="uq_industry_metric_profile",
        ),
        Index("ix_industry_metric_profiles_profile_key", "profile_key"),
        Index("ix_industry_metric_profiles_egx_sector_id", "egx_sector_id"),
        Index("ix_industry_metric_profiles_sub_industry_id", "sub_industry_id"),
    )
