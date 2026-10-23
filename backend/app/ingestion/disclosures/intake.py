"""Disclosure intake: explicit registration + upload with sha256 dedupe (R34 P0-1).

Intake is manual only: callers register a URL or upload bytes. Nothing here
fetches, crawls, or schedules — URL registrations hash the canonical URL
string (no download), uploads hash the raw bytes. Same bytes twice resolve to
the single stored row. Cross-path dedupe (URL-then-upload of the same PDF) is
out of scope for v1 and stays two rows.
"""

import hashlib
import uuid
from datetime import UTC, date, datetime
from urllib.parse import urlparse

from app.ingestion.disclosures.constants import (
    ACCOUNTING_BASES,
    FILING_TYPES,
    MAX_PDF_BYTES,
)


def compute_content_hash(data: bytes) -> str:
    """sha256 hex digest of raw PDF bytes (the upload dedupe key)."""
    return hashlib.sha256(data).hexdigest()


def registration_hash_for_url(filing_url: str) -> str:
    """Stable identity for URL-only registrations (the URL is never fetched)."""
    return hashlib.sha256(filing_url.strip().encode("utf-8")).hexdigest()


def validate_filing_type(filing_type: str) -> str:
    """Return the filing type or raise; unknown types are rejected, not guessed."""
    if filing_type not in FILING_TYPES:
        raise ValueError(f"Unknown filing_type {filing_type!r}; expected one of {FILING_TYPES}")
    return filing_type


def validate_accounting_basis(accounting_basis: str) -> str:
    """Return the accounting basis or raise; never defaulted silently."""
    if accounting_basis not in ACCOUNTING_BASES:
        raise ValueError(
            f"Unknown accounting_basis {accounting_basis!r}; expected one of {ACCOUNTING_BASES}"
        )
    return accounting_basis


PDF_MAGIC = b"%PDF-"
ALLOWED_URL_SCHEMES = ("http", "https")


def check_upload_bytes(data: bytes, *, filename: str) -> bytes:
    """Trust-boundary checks for an uploaded PDF: non-empty, within size cap, PDF magic."""
    if not data:
        raise ValueError(f"Empty upload for {filename!r}: nothing to register")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError(
            f"Upload for {filename!r} is {len(data)} bytes, over the "
            f"{MAX_PDF_BYTES} byte cap"
        )
    if not data.startswith(PDF_MAGIC):
        raise ValueError(f"Upload for {filename!r} is not a PDF (missing %PDF- header)")
    return data


def validate_filing_url(filing_url: str) -> str:
    """Return the stripped URL or raise; only absolute http(s) URLs are registered."""
    url = filing_url.strip()
    if not url:
        raise ValueError("filing_url is required for URL registration")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES or not parsed.netloc:
        raise ValueError("filing_url must be an absolute http(s) URL")
    return url


def new_filing_id() -> uuid.UUID:
    """One UUID per registry row (single place the id is minted)."""
    return uuid.uuid4()


def downloaded_now() -> datetime:
    """Download timestamp pinned at registration time (UTC, ISO-serializable)."""
    return datetime.now(UTC)


def filing_period_bounds(
    report_date: date, filing_type: str
) -> tuple[str, int, int | None, date, date]:
    """Calendar grouping key for a filing: (period_type, fiscal_year, quarter, start, end).

    Bounds are deterministic calendar conventions for grouping facts into
    Phase-1 periods — not financial values. BOARD/AGM/MATERIAL filings group
    into INTERIM on their report date.
    """
    year = report_date.year
    if filing_type == "FY":
        return ("ANNUAL", year, None, date(year, 1, 1), date(year, 12, 31))
    if filing_type == "H1":
        return ("SEMI_ANNUAL", year, None, date(year, 1, 1), date(year, 6, 30))
    if filing_type == "9M":
        return ("INTERIM", year, None, date(year, 1, 1), date(year, 9, 30))
    if filing_type == "Q":
        quarter = (report_date.month - 1) // 3 + 1
        starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
        ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
        start = date(year, *starts[quarter])
        end = date(year, *ends[quarter])
        return (f"Q{quarter}", year, quarter, start, end)
    return ("INTERIM", year, None, report_date, report_date)
