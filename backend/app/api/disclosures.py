"""API endpoints for Phase-7 document intelligence (R34 P0-1–P0-6)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.ingestion.disclosures.constants import DISCLOSURE_METHODOLOGY_VERSION, MAX_PDF_BYTES
from app.ingestion.disclosures.service import DisclosureService

router = APIRouter(prefix="/api/disclosures", tags=["disclosures"])


class RegisterBody(BaseModel):
    """Explicit URL registration (no fetch: the registry mirrors, never crawls)."""

    company_id: uuid.UUID
    filing_url: str
    bulletin_id: str | None = None
    report_date: date
    filing_type: str = "Q"
    accounting_basis: str = "EAS"
    content_hash: str | None = None


class ParseBody(BaseModel):
    """Parse options for stored upload bytes (pdfplumber-first v1)."""

    engine: str = "pdfplumber"
    method: str = "lattice"
    statement_pages: dict[str, list[int]] = Field(default_factory=dict)
    metrics: list[str] | None = None
    fact_type: str = "INCOME_STATEMENT"
    currency: str = "EGP"
    audit_state: str = "unaudited"
    eas_tags: list[str] = Field(default_factory=list)


class FactBody(BaseModel):
    """One parsed cell recorded with full provenance (missing value → UNKNOWN)."""

    filing_id: uuid.UUID
    metric: str
    value: float | None = None
    statement_name: str = "income_statement"
    page: int | None = None
    table_id: int | None = None
    row: int | None = None
    col: int | None = None
    fact_type: str = "INCOME_STATEMENT"
    currency: str = "EGP"
    audit_state: str = "unaudited"
    eas_tags: list[str] = Field(default_factory=list)
    estimate: float | None = None


def _dec(value: float | None) -> Decimal | None:
    """Body float to Decimal; None stays None and zero stays zero."""
    return Decimal(str(value)) if value is not None else None


UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _read_capped(file: UploadFile) -> bytes:
    """Read the upload in chunks, refusing (413) as soon as it passes the byte cap."""
    buffer = bytearray()
    while chunk := await file.read(UPLOAD_CHUNK_BYTES):
        buffer.extend(chunk)
        if len(buffer) > MAX_PDF_BYTES:
            raise HTTPException(
                status_code=413, detail=f"Upload exceeds the {MAX_PDF_BYTES} byte cap"
            )
    return bytes(buffer)


def _service(session: AsyncSession) -> DisclosureService:
    return DisclosureService(session)


@router.post("/register")
async def register_filing(
    body: RegisterBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Register a disclosure URL explicitly. Same content hash twice → one row."""
    try:
        filing, created = await _service(session).register_url(
            company_id=body.company_id,
            filing_url=body.filing_url,
            bulletin_id=body.bulletin_id,
            report_date=body.report_date,
            filing_type=body.filing_type,
            accounting_basis=body.accounting_basis,
            content_hash=body.content_hash,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"filing": DisclosureService.filing_payload(filing), "created": created}


@router.post("/upload")
async def upload_filing(
    company_id: uuid.UUID = Form(...),
    report_date: date = Form(...),
    filing_type: str = Form("Q"),
    accounting_basis: str = Form("EAS"),
    bulletin_id: str | None = Form(None),
    auto_parse: bool = Form(True),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Upload a disclosure PDF into the registry mirror. Same bytes twice → one row.

    With ``auto_parse`` (default) the stored bytes are parsed right away with the
    default parse options; a parse failure never fails the upload. Parsed facts
    land in ``financial_facts`` and do not feed the engines (R43 section 1.1).
    """
    try:
        filing, created = await _service(session).upload(
            company_id=company_id,
            filename=file.filename or "filing.pdf",
            data=await _read_capped(file),
            bulletin_id=bulletin_id,
            report_date=report_date,
            filing_type=filing_type,
            accounting_basis=accounting_basis,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    parse: dict[str, Any] | None = None
    if auto_parse:
        defaults = ParseBody()
        try:
            async with session.begin_nested():
                parse = await _service(session).parse_filing(
                    filing.id,
                    engine=defaults.engine,
                    method=defaults.method,
                    statement_pages=defaults.statement_pages or None,
                    metrics=defaults.metrics,
                    fact_type=defaults.fact_type,
                    currency=defaults.currency,
                    audit_state=defaults.audit_state,
                    eas_tags=defaults.eas_tags,
                )
        except Exception as exc:  # noqa: BLE001 - a parse failure never fails the upload
            parse = {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}
    return {
        "filing": DisclosureService.filing_payload(filing),
        "created": created,
        "parse": parse,
    }


@router.get("/filings")
async def list_filings(
    company_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List the intake registry rows for one company."""
    try:
        return await _service(session).list_filings(company_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/filings/{filing_id}/parse")
async def parse_filing(
    filing_id: uuid.UUID,
    body: ParseBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Parse stored upload bytes with the rule-based engine and persist cells.

    Scanned PDFs return UNKNOWN ``{scanned-needs-OCR}`` with no facts stored.
    """
    try:
        return await _service(session).parse_filing(
            filing_id,
            engine=body.engine,
            method=body.method,
            statement_pages=body.statement_pages or None,
            metrics=body.metrics,
            fact_type=body.fact_type,
            currency=body.currency,
            audit_state=body.audit_state,
            eas_tags=body.eas_tags,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/facts")
async def record_fact(
    body: FactBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Record one parsed cell with full provenance (restatement-aware)."""
    try:
        fact, created, diff = await _service(session).record_fact(
            filing_id=body.filing_id,
            metric=body.metric,
            value=_dec(body.value),
            statement_name=body.statement_name,
            page=body.page,
            table_id=body.table_id,
            row=body.row,
            col=body.col,
            fact_type=body.fact_type,
            currency=body.currency,
            audit_state=body.audit_state,
            eas_tags=body.eas_tags,
            estimate=_dec(body.estimate),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "fact_id": str(fact.id),
        "created": created,
        "is_restated": fact.is_restated,
        "supersedes": str(fact.supersedes_id) if fact.supersedes_id else None,
        "diff_id": str(diff.id) if diff is not None else None,
    }


@router.get("/facts")
async def list_facts(
    company_id: uuid.UUID = Query(...),
    metric: str | None = Query(None),
    as_of: datetime | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Provenance facts for one company; ``as_of`` returns pre-restatement values."""
    try:
        return await _service(session).list_fact_payloads(
            company_id, metric=metric, as_of=as_of
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/comparison")
async def get_comparison(
    company_id: uuid.UUID = Query(...),
    metric: str = Query("revenue"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Deterministic TTM + YoY deltas plus the TTM-margin-vs-prior-year block.

    Mixing EAS-family with IFRS facts in one series is refused (422), never
    silently pooled.
    """
    service = _service(session)
    try:
        comparison = await service.compare(company_id, metric)
        margin = await service.margin_block(company_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"comparison": comparison, "ttm_margin_vs_prior_year": margin}


@router.get("/diffs")
async def list_diffs(
    company_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """The append-only "what changed?" ledger for one company, newest first."""
    try:
        return await _service(session).list_diffs(company_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def methodology_version() -> str:
    """Re-exported for contract tests pinning the version echo."""
    return DISCLOSURE_METHODOLOGY_VERSION
