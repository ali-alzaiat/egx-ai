from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DailyPriceBase(BaseModel):
    date: date
    open: Decimal = Field(..., decimal_places=4)
    high: Decimal = Field(..., decimal_places=4)
    low: Decimal = Field(..., decimal_places=4)
    close: Decimal = Field(..., decimal_places=4)
    adjusted_close: Decimal | None = Field(None, decimal_places=4)
    volume: int = Field(..., ge=0)
    value_traded: Decimal | None = Field(None, decimal_places=2)
    trades: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def validate_ohlc(self) -> "DailyPriceBase":
        if self.low > self.open:
            raise ValueError("low must be <= open")
        if self.low > self.high:
            raise ValueError("low must be <= high")
        if self.open > self.high:
            raise ValueError("open must be <= high")
        if self.close > self.high:
            raise ValueError("close must be <= high")
        if self.close < self.low:
            raise ValueError("close must be >= low")
        return self


class DailyPriceCreate(DailyPriceBase):
    company_id: UUID
    source_id: UUID


class DailyPriceRead(DailyPriceBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    source_id: UUID
    created_at: datetime


class DailyPriceListParams(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(200, ge=1, le=1000)


class PaginatedResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int
