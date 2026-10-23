"""EGX33 Shariah membership snapshot loader and the shared Shariah status block."""

import uuid
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import Company, CompanyStatus
from app.models.screening import ScreeningEgxMembership
from app.screening.egx33 import CONSTITUENTS, REVIEW_CYCLE, SOURCE_URL, load_snapshot
from app.screening.status import NOT_MEMBER_COPY, shariah_status, shariah_statuses


class TestSnapshot:
    def test_snapshot_is_well_formed(self) -> None:
        tickers = [t for t, _, _ in CONSTITUENTS]
        isins = [i for _, i, _ in CONSTITUENTS]
        assert len(CONSTITUENTS) == 34  # 33 companies; FAIT has EGP and USD lines
        assert len(set(tickers)) == len(tickers)
        assert len(set(isins)) == len(isins)
        assert all(i.startswith("EGS") and len(i) == 12 for i in isins)
        assert REVIEW_CYCLE[-2:] in {"02", "08"}
        assert SOURCE_URL.startswith("https://www.egx.com.eg/")

    async def test_load_matches_by_isin_and_is_idempotent(self, db_session: AsyncSession) -> None:
        # A company whose ticker differs but ISIN matches ADIB's must still be matched.
        company = Company(
            id=uuid.uuid4(),
            ticker=f"ZZ{uuid.uuid4().hex[:6].upper()}",
            isin="EGS60111C019",
            name="ISIN match probe",
            currency="EGP",
            status=CompanyStatus.ACTIVE,
        )
        existing = await db_session.scalar(select(Company).where(Company.isin == company.isin))
        if existing is None:
            db_session.add(company)
            await db_session.flush()
            probe_id = company.id
        else:
            probe_id = existing.id

        recorded, unmatched = await load_snapshot(db_session)
        assert sorted(recorded + unmatched) == sorted(t for t, _, _ in CONSTITUENTS)
        assert "ADIB" in recorded

        await load_snapshot(db_session)  # second run: upsert, no duplicates
        count = await db_session.scalar(
            select(func.count(ScreeningEgxMembership.id)).where(
                ScreeningEgxMembership.company_id == probe_id,
                ScreeningEgxMembership.review_cycle == REVIEW_CYCLE,
            )
        )
        assert count == 1

    async def test_load_records_non_members(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        await load_snapshot(db_session)
        row = await db_session.scalar(
            select(ScreeningEgxMembership).where(
                ScreeningEgxMembership.company_id == test_company.id,
                ScreeningEgxMembership.review_cycle == REVIEW_CYCLE,
            )
        )
        assert row is not None and row.member is False

    async def test_newer_record_for_one_company_does_not_demote_others(
        self, db_session: AsyncSession
    ) -> None:
        companies = [
            Company(
                id=uuid.uuid4(),
                ticker=f"ZZ{uuid.uuid4().hex[:6].upper()}",
                name=f"probe {i}",
                currency="EGP",
                status=CompanyStatus.ACTIVE,
            )
            for i in range(2)
        ]
        db_session.add_all(companies)
        await db_session.flush()
        first, second = companies
        for company, cycle in ((first, "2026-08"), (second, "2026-08"), (second, "2099-02")):
            db_session.add(
                ScreeningEgxMembership(
                    company_id=company.id,
                    methodology_version="test",
                    member=True,
                    review_cycle=cycle,
                    source="https://www.egx.com.eg/test",
                )
            )
        await db_session.flush()

        blocks = await shariah_statuses(db_session, [first.id, second.id])
        assert blocks[first.id]["egx33"] == "member"
        assert blocks[first.id]["egx33_review_cycle"] == "2026-08"
        assert blocks[second.id]["egx33_review_cycle"] == "2099-02"


def _verdict(status: str) -> Any:
    return SimpleNamespace(status=SimpleNamespace(value=status), methodology_version="aaoifi-x")


def _membership(member: bool) -> Any:
    return SimpleNamespace(
        member=member, source="https://www.egx.com.eg/x", review_cycle="2026-08"
    )


class TestShariahStatus:
    def test_unknown_when_never_recorded(self) -> None:
        block = shariah_status(None, None)
        assert block["egx33"] == "unknown"
        assert block["verdict"] == "NOT_SCREENED"
        assert block["note"] is None

    def test_member(self) -> None:
        block = shariah_status(None, _membership(True))
        assert block["egx33"] == "member"
        assert block["egx33_review_cycle"] == "2026-08"
        assert block["egx33_source"] == "https://www.egx.com.eg/x"

    def test_recorded_non_member_has_non_verdict_note(self) -> None:
        block = shariah_status(None, _membership(False))
        assert block["egx33"] == "not_member"
        assert block["note"] == NOT_MEMBER_COPY

    def test_our_verdict_reported_independently(self) -> None:
        block = shariah_status(_verdict("NON_COMPLIANT"), _membership(True))
        # EGX33 membership never overrides our own verdict, and vice versa.
        assert block["verdict"] == "NON_COMPLIANT"
        assert block["methodology_version"] == "aaoifi-x"
        assert block["egx33"] == "member"
