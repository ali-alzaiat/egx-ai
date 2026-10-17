"""Pydantic schemas for statement review queue and assembled statements."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class ReviewQueueItemRead(BaseModel):
    """One candidate in the Ops review queue, with provenance."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    period_id: uuid.UUID
    ontology_code: str
    ontology_version: str
    value: str | None
    currency: str
    source_label_reported: str | None
    source_label_en: str | None
    source_label_ar: str | None
    source_page: str | None
    extraction_method: str
    published_date: date | None
    document_url: str | None
    document_type: str | None


class ReviewDecisionRequest(BaseModel):
    """Body of a reject decision (approve takes no extra fields)."""

    reason: str | None = None


class ReviewDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ontology_code: str
    ext_status: str
    ext_reason: str | None
