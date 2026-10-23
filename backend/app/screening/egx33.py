"""Official EGX33 Shariah Index membership snapshot and loader.

Source: the Egyptian Exchange "current index constituents" page for the EGX 33
Shariah index, read on ``FETCHED_ON``. The page publishes ISIN, Reuters code and
company name but no effective date, so the snapshot is filed under the latest
semi-annual review cycle at fetch time and the gap is recorded in the note.

Membership is EGX's verdict, shown beside ours and never overriding it.
Absence from the index is not a non-compliance verdict: the index only covers
EGX100 names (plus Shariah-board companies) and caps at ~33 members.

Usage:
    python -m app.screening.egx33        # record the snapshot (idempotent)
"""

import asyncio
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import Company
from app.repositories.screening import ScreeningRepository
from app.screening.methodology import DEFAULT_METHODOLOGY

logger = logging.getLogger(__name__)

SOURCE_URL = "https://www.egx.com.eg/en/currentindexconstituntes.aspx?type=22&nav=22"
FETCHED_ON = date(2026, 10, 23)
REVIEW_CYCLE = "2026-08"
SNAPSHOT_NOTE = (
    f"EGX 'current constituents' page read {FETCHED_ON.isoformat()}; the page carries "
    "no effective date. EGX's Sep-2026 semi-annual review press release lists CLHO "
    "and GOUR among EGX33 Shariah deletions while this page still lists them: "
    "unreconciled, re-check at the next review."
)

# (ticker, ISIN, company name) exactly as published; FAIT trades in EGP and USD lines.
CONSTITUENTS: tuple[tuple[str, str, str], ...] = (
    ("ADIB", "EGS60111C019", "Abu Dhabi Islamic Bank- Egypt"),
    ("SAUD", "EGS60101C010", "Al Baraka Bank Egypt"),
    ("AMOC", "EGS380P1C010", "Alexandria Mineral Oils Company"),
    ("ACGC", "EGS32221C011", "Arab Cotton Ginning"),
    ("ARCC", "EGS3C0O1C016", "Arabian Cement Company"),
    ("CLHO", "EGS729J1C018", "Cleopatra Hospital Company"),
    ("EFID", "EGS305I1C011", "Edita Food Industries S.A.E"),
    ("EFIH", "EGS743O1C013", "E-finance For Digital and Financial Investments"),
    ("EGAL", "EGS3E181C010", "Egypt Aluminum"),
    ("ETRS", "EGS42051C010", "Egyptian Transport & Commercial Services Co. -EGYTRANS NOSCO"),
    ("FAIT", "EGS60321C014", "Faisal Islamic Bank of Egypt - In EGP"),
    ("FAITA", "EGS60322C012", "Faisal Islamic Bank of Egypt - In US Dollars"),
    ("GOUR", "EGS540S1C014", "Gourmet Egypt.Com Foods"),
    ("ISPH", "EGS512O1C012", "Ibnsina Pharma"),
    ("IFAP", "EGS07061C012", "International Agricultural Products"),
    ("ICFC", "EGS520D1C015", "International Company For Fertilizers & Chemicals"),
    ("JUFO", "EGS30901C010", "Juhayna Food Industries"),
    ("LCSW", "EGS3C161C014", "Lecico Egypt"),
    ("MASR", "EGS65571C019", "Madinet Masr For Housing and Development"),
    ("MPCO", "EGS02091C014", "Mansourah Poultry"),
    ("MCQE", "EGS3C391C017", "Misr Cement (Qena)"),
    ("ATQA", "EGS3D0C1C018", "Misr National Steel - Ataqa"),
    ("MTIE", "EGS75011C014", "MM Group For Industry And International Trade"),
    ("EGAS", "EGS39011C019", "Natural Gas & Mining Project (Egypt Gas)"),
    ("ORAS", "EGS95001C011", "Orascom Construction PLC"),
    ("ORHD", "EGS70321C012", "Orascom Development Egypt"),
    ("ORWE", "EGS33041C012", "Oriental Weavers"),
    ("PHDC", "EGS655L1C012", "Palm Hills Development Company"),
    ("RACC", "EGS74191C015", "Raya Customer Experience"),
    ("SKPC", "EGS380S1C017", "Sidi Kerir Petrochemicals - SIDPEC"),
    ("OCDI", "EGS65851C015", "Six of October Development & Investment (SODIC)"),
    ("TMGH", "EGS691S1C011", "T M G Holding"),
    ("ETEL", "EGS48031C016", "Telecom Egypt"),
    ("RMDA", "EGS381B1C015", "Tenth Of Ramadan Pharmaceutical Industries&Diagnostic-Rameda"),
)


NON_MEMBER_NOTE = (
    f"Not on the EGX33 Shariah constituents page read {FETCHED_ON.isoformat()}. "
    "Absence from the index is not a non-compliance verdict."
)


async def load_snapshot(session: AsyncSession) -> tuple[list[str], list[str]]:
    """Record the snapshot for ``REVIEW_CYCLE``: constituents as members, every
    other known company as a non-member.

    Recording non-members per cycle means a company dropped at a later review
    flips to "not_member" instead of keeping its stale "member" row.
    Companies are matched by ISIN first, then ticker. Returns (recorded, unmatched)
    constituent tickers; unmatched constituents are reported, never invented.
    """
    isins = [isin for _, isin, _ in CONSTITUENTS]
    tickers = [ticker for ticker, _, _ in CONSTITUENTS]
    rows = (
        await session.execute(
            select(Company).where(Company.isin.in_(isins) | Company.ticker.in_(tickers))
        )
    ).scalars().all()
    by_isin = {c.isin: c.id for c in rows if c.isin}
    by_ticker = {c.ticker: c.id for c in rows}

    repo = ScreeningRepository(session)
    recorded: list[str] = []
    unmatched: list[str] = []
    for ticker, isin, _name in CONSTITUENTS:
        company_id = by_isin.get(isin) or by_ticker.get(ticker)
        if company_id is None:
            unmatched.append(ticker)
            continue
        await repo.upsert_egx_membership(
            company_id=company_id,
            methodology_version=DEFAULT_METHODOLOGY.version.value,
            member=True,
            review_cycle=REVIEW_CYCLE,
            effective_date=None,
            source=SOURCE_URL,
            note=SNAPSHOT_NOTE,
        )
        recorded.append(ticker)

    member_ids = {by_isin.get(isin) or by_ticker.get(ticker) for ticker, isin, _ in CONSTITUENTS}
    all_ids = (await session.execute(select(Company.id))).scalars().all()
    for company_id in all_ids:
        if company_id in member_ids:
            continue
        await repo.upsert_egx_membership(
            company_id=company_id,
            methodology_version=DEFAULT_METHODOLOGY.version.value,
            member=False,
            review_cycle=REVIEW_CYCLE,
            effective_date=None,
            source=SOURCE_URL,
            note=NON_MEMBER_NOTE,
        )
    return recorded, unmatched


async def _main() -> None:
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        recorded, unmatched = await load_snapshot(session)
        await session.commit()
    print(f"EGX33 Shariah snapshot {REVIEW_CYCLE}: recorded {len(recorded)}")
    if unmatched:
        print(f"Unmatched constituents (no company row): {', '.join(unmatched)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
