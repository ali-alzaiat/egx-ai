from typing import Any

from pydantic import BaseModel, Field


class PaginatedResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int


class PriceQueryParams(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(200, ge=1, le=1000)
