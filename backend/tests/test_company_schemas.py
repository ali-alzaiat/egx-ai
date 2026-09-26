"""Tests for company schemas."""

from app.models.market import CompanyStatus
from app.schemas.company import CompanyCreate, CompanyUpdate


class TestCompanyCreate:
    def test_create_company(self) -> None:
        company = CompanyCreate(
            ticker="COMI",
            name="Commercial International Bank",
            sector="Financials",
            industry="Banks",
        )
        assert company.ticker == "COMI"
        assert company.name == "Commercial International Bank"
        assert company.currency == "EGP"
        assert company.status == CompanyStatus.ACTIVE

    def test_create_company_minimal(self) -> None:
        company = CompanyCreate(
            ticker="TEST",
            name="Test Company",
        )
        assert company.ticker == "TEST"
        assert company.isin is None
        assert company.name_ar is None
        assert company.listing_date is None

    def test_create_company_with_isin(self) -> None:
        company = CompanyCreate(
            ticker="COMI",
            name="Commercial International Bank",
            isin="EGY000111016",
        )
        assert company.isin == "EGY000111016"


class TestCompanyUpdate:
    def test_update_partial(self) -> None:
        update = CompanyUpdate(sector="Technology")
        data = update.model_dump(exclude_unset=True)
        assert data == {"sector": "Technology"}

    def test_update_empty(self) -> None:
        update = CompanyUpdate()
        data = update.model_dump(exclude_unset=True)
        assert data == {}
