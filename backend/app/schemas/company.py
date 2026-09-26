from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.market import CompanyStatus


class CompanyBase(BaseModel):
    ticker: str = Field(..., max_length=20)
    isin: str | None = Field(None, max_length=12)
    name: str = Field(..., max_length=255)
    name_ar: str | None = Field(None, max_length=255)
    sector: str | None = Field(None, max_length=100)
    industry: str | None = Field(None, max_length=100)
    currency: str = Field("EGP", max_length=3)
    shares_outstanding: Decimal | None = None
    free_float: Decimal | None = None
    listing_date: date | None = None
    status: CompanyStatus = CompanyStatus.ACTIVE


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    isin: str | None = None
    name: str | None = None
    name_ar: str | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None
    shares_outstanding: Decimal | None = None
    free_float: Decimal | None = None
    listing_date: date | None = None
    status: CompanyStatus | None = None


class CompanyRead(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class CompanyListParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=200)
    sector: str | None = None
    industry: str | None = None
    status: CompanyStatus | None = None
    search: str | None = None
