"""Tiered entitlement constants (zborsa plan Task 10).

Pure unit tests: the seeded numbers are contractual — the Pricing page,
the frontend paywall copy, and the FREE quota cut all read these values.
"""

from __future__ import annotations

import dataclasses

from app.billing.entitlements import PLAN_ENTITLEMENTS, Entitlements, PlanTier


class TestPlanEntitlements:
    def test_free_tier_exact_numbers(self) -> None:
        free = PLAN_ENTITLEMENTS[PlanTier.FREE]
        assert free.daily_stance_quota == 3
        assert free.daily_radar == 1
        assert free.company_hub_full is False

    def test_paid_tiers_unlimited(self) -> None:
        for tier in (PlanTier.PRO, PlanTier.MAX):
            ent = PLAN_ENTITLEMENTS[tier]
            assert ent.daily_stance_quota == 10_000
            assert ent.daily_radar == 100_000
            assert ent.company_hub_full is True

    def test_keys_match_tiers_exactly(self) -> None:
        assert set(PLAN_ENTITLEMENTS) == {
            PlanTier.FREE,
            PlanTier.PRO,
            PlanTier.MAX,
        }

    def test_entitlements_frozen(self) -> None:
        free = PLAN_ENTITLEMENTS[PlanTier.FREE]
        assert dataclasses.is_dataclass(free)
        try:
            free.daily_stance_quota = 99  # type: ignore[misc]
            raise AssertionError("Entitlements must be immutable")
        except dataclasses.FrozenInstanceError:
            pass

    def test_entitlement_field_names_stable(self) -> None:
        fields = {f.name for f in dataclasses.fields(Entitlements)}
        assert fields == {"daily_stance_quota", "daily_radar", "company_hub_full"}
