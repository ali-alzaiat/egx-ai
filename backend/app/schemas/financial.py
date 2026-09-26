from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.financial import (
    DocumentStatus,
    FactStatus,
    FactType,
    ReportingPeriodType,
)


class FinancialPeriodBase(BaseModel):
    company_id: UUID
    period_type: ReportingPeriodType
    fiscal_year: int = Field(..., ge=1900, le=2100)
    fiscal_quarter: int | None = Field(None, ge=1, le=4)
    start_date: date
    end_date: date


class FinancialPeriodCreate(FinancialPeriodBase):
    pass


class FinancialPeriodRead(FinancialPeriodBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class FinancialDocumentBase(BaseModel):
    period_id: UUID
    source_id: UUID
    document_status: DocumentStatus = DocumentStatus.ORIGINAL
    document_type: str = Field(..., max_length=50)
    document_url: str | None = Field(None, max_length=500)
    filing_date: date | None = None
    publication_date: date | None = None
    fiscal_year_end: date | None = None
    notes: str | None = None


class FinancialDocumentCreate(FinancialDocumentBase):
    pass


class FinancialDocumentRead(FinancialDocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class FinancialFactBase(BaseModel):
    period_id: UUID
    document_id: UUID
    company_id: UUID
    fact_type: FactType
    reported_label: str = Field(..., max_length=255)
    normalized_label: str | None = Field(None, max_length=255)
    reported_value: Decimal | None = Field(None, decimal_places=4)
    normalized_value: Decimal | None = Field(None, decimal_places=4)
    currency: str = Field("EGP", max_length=3)
    unit: str | None = Field(None, max_length=50)
    scale: int | None = None
    status: FactStatus = FactStatus.REPORTED
    source_page: str | None = Field(None, max_length=100)
    source_line: str | None = Field(None, max_length=100)
    reported_at: datetime | None = None
    normalized_at: datetime | None = None


class FinancialFactCreate(FinancialFactBase):
    pass


class FinancialFactRead(FinancialFactBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class FinancialFactUpdate(BaseModel):
    normalized_label: str | None = None
    normalized_value: Decimal | None = None
    status: FactStatus | None = None
    normalized_at: datetime | None = None


class FinancialPeriodListParams(BaseModel):
    company_id: UUID
    period_type: ReportingPeriodType | None = None
    fiscal_year: int | None = None


class FinancialDocumentListParams(BaseModel):
    period_id: UUID
    document_status: DocumentStatus | None = None
    fiscal_year: int | None = None


class FinancialFactListParams(BaseModel):
    company_id: UUID
    fact_type: FactType | None = None
    reported_label: str | None = None
    normalized_label: str | None = None
    status: FactStatus | None = None
    fiscal_year: int | None = None
