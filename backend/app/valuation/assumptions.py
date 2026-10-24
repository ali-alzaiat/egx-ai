"""Sourced valuation assumptions (R43 section 1.6, R44 (b), R45 M5): versioned record.

Stored, sourced inputs (each row has a source URL, title and as-of date; never a
code constant, AGENTS rules 2 and 5): ``risk_free_rate``, ``equity_risk_premium``,
``long_run_inflation``, ``long_run_cost_of_equity``, ``nominal_gdp_growth`` (the cap on
the 3-year revenue CAGR used as stage-1 growth, owner ruling F13) and the
relative-multiple targets. Computed in code from them (R44 (b)):

- ``discount_rate``        = ``risk_free_rate`` + ``equity_risk_premium`` (explicit stage)
- ``terminal_growth_rate`` = ``stable_growth`` = ``long_run_inflation``
- ``long_run_cost_of_equity`` capitalises the terminal value (R45 M5 fade)

Staleness (R44 (b)): the yield row older than 120 days, the other rows older than
400 days count as missing with the reason "stale assumption". With no fresh row
the legs that need the value are INSUFFICIENT_DATA naming it.

Resolution: a profile-scoped row beats a ``market`` row; the newest
``as_of <= today`` wins; nothing found -> None.

Usage (the only writer; no UI):
    python -m app.valuation.assumptions set --key risk_free_rate --scope market \\
        --value 0.24 --source-url https://... --source-title "..." --as-of 2026-10-01
    python -m app.valuation.assumptions list
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.valuation import ValuationAssumption
from app.valuation.constants import VALUATION_METHODOLOGY_VERSION, VALUATION_PROFILES

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

ASSUMPTION_KEYS: tuple[str, ...] = (
    "risk_free_rate",
    "equity_risk_premium",
    "long_run_inflation",
    "long_run_cost_of_equity",
    "nominal_gdp_growth",
    "target_pe",
    "target_pb",
    "target_ps",
)
MARKET_SCOPE = "market"

#: R44 (b): a yield row goes stale after 120 days, the other sourced rows after 400.
#: ``long_run_cost_of_equity`` is built from annual sources (Damodaran, IMF): 400.
MAX_AGE_DAYS: dict[str, int] = {
    "risk_free_rate": 120,
    "equity_risk_premium": 400,
    "long_run_inflation": 400,
    "long_run_cost_of_equity": 400,
    "nominal_gdp_growth": 400,
}

#: Computed keys -> the stored keys they are built from.
DERIVED_FROM: dict[str, tuple[str, ...]] = {
    "discount_rate": ("risk_free_rate", "equity_risk_premium"),
    "terminal_growth_rate": ("long_run_inflation",),
    "stable_growth": ("long_run_inflation",),
}


@dataclass(frozen=True, slots=True)
class AssumptionItem:
    id: uuid.UUID
    key: str
    scope: str
    value: Decimal
    source_url: str
    source_title: str
    as_of: date

    def as_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "scope": self.scope,
            "value": str(self.value),
            "source_url": self.source_url,
            "source_title": self.source_title,
            "as_of": self.as_of.isoformat(),
        }

    def provenance(self) -> str:
        return f"assumption:{self.key} {self.scope} as_of {self.as_of.isoformat()}"


@dataclass(frozen=True, slots=True)
class AssumptionSet:
    """Fresh resolved rows (``items``) plus the stale ones (``stale``: key -> reason)."""

    items: dict[str, AssumptionItem]
    stamp: str
    stale: dict[str, str] = field(default_factory=dict)

    def value(self, key: str) -> Decimal | None:
        item = self.items.get(key)
        return item.value if item is not None else None

    @property
    def missing(self) -> list[str]:
        """Stored keys with no fresh row (stale rows are listed here too)."""
        return [k for k in ASSUMPTION_KEYS if k not in self.items]

    @property
    def discount_rate(self) -> Decimal | None:
        """Explicit-stage cost of equity = risk-free rate + equity risk premium."""
        rf = self.value("risk_free_rate")
        erp = self.value("equity_risk_premium")
        return rf + erp if rf is not None and erp is not None else None

    @property
    def terminal_growth_rate(self) -> Decimal | None:
        """Zero real growth: terminal (and stable) growth = long-run inflation."""
        return self.value("long_run_inflation")

    @property
    def long_run_cost_of_equity(self) -> Decimal | None:
        return self.value("long_run_cost_of_equity")

    def provenance_of(self, key: str) -> str | None:
        """Provenance string of a stored or computed key; None when unavailable."""
        sources = DERIVED_FROM.get(key, (key,))
        if any(k not in self.items for k in sources):
            return None
        return " + ".join(self.items[k].provenance() for k in sources)

    def gap(self, keys: Sequence[str]) -> str:
        """Reason naming each stored key that is missing or stale."""
        absent = [k for k in keys if k not in self.items and k not in self.stale]
        parts = [f"no sourced {', '.join(absent)}"] if absent else []
        parts.extend(self.stale[k] for k in keys if k in self.stale)
        return "; ".join(parts) + f" in valuation assumptions {VALUATION_METHODOLOGY_VERSION}"

    def payload(self) -> dict[str, object]:
        discount = self.discount_rate
        return {
            "methodology_version": VALUATION_METHODOLOGY_VERSION,
            "items": [self.items[k].as_dict() for k in ASSUMPTION_KEYS if k in self.items],
            "missing": self.missing,
            "stale": [{"key": k, "reason": v} for k, v in self.stale.items()],
            "computed": {
                "discount_rate": str(discount) if discount is not None else None,
                "terminal_growth_rate": (
                    str(self.terminal_growth_rate)
                    if self.terminal_growth_rate is not None
                    else None
                ),
                "formula": "discount_rate = risk_free_rate + equity_risk_premium; "
                "terminal_growth_rate = long_run_inflation",
            },
        }


async def resolve_assumptions(
    session: AsyncSession, profile_key: str, today: date | None = None
) -> AssumptionSet:
    """Resolve each key: profile scope beats market, newest ``as_of <= today``."""
    today = today or datetime.now(UTC).date()
    rows = (
        await session.execute(
            select(ValuationAssumption)
            .where(ValuationAssumption.methodology_version == VALUATION_METHODOLOGY_VERSION)
            .where(ValuationAssumption.scope.in_((profile_key, MARKET_SCOPE)))
            .where(ValuationAssumption.as_of <= today)
            .order_by(ValuationAssumption.as_of.desc(), ValuationAssumption.recorded_at.desc())
        )
    ).scalars().all()
    items: dict[str, AssumptionItem] = {}
    for scope in (profile_key, MARKET_SCOPE):
        for row in rows:
            if row.scope != scope or row.key in items:
                continue
            items[row.key] = AssumptionItem(
                id=row.id,
                key=row.key,
                scope=row.scope,
                value=Decimal(row.value),
                source_url=row.source_url,
                source_title=row.source_title,
                as_of=row.as_of,
            )
    stale: dict[str, str] = {}
    for key, max_age in MAX_AGE_DAYS.items():
        item = items.get(key)
        if item is not None and (today - item.as_of).days > max_age:
            stale[key] = (
                f"stale assumption: {key} as of {item.as_of.isoformat()} is older than "
                f"{max_age} days"
            )
            del items[key]
    stamp = ",".join(sorted(str(i.id) for i in items.values()))
    return AssumptionSet(items=items, stamp=stamp, stale=stale)


def validate_assumption(key: str, scope: str, source_url: str, source_title: str) -> None:
    if key not in ASSUMPTION_KEYS:
        raise ValueError(f"unknown assumption key {key!r}; expected one of {ASSUMPTION_KEYS}")
    if scope != MARKET_SCOPE and scope not in VALUATION_PROFILES:
        raise ValueError(
            f"scope must be 'market' or a valuation profile ({', '.join(VALUATION_PROFILES)})"
        )
    if not source_url.startswith("http"):
        raise ValueError("source_url must be the http(s) address of the source")
    if not source_title.strip():
        raise ValueError("source_title is required")


async def record_assumption(
    session: AsyncSession,
    *,
    key: str,
    scope: str,
    value: Decimal,
    source_url: str,
    source_title: str,
    as_of: date,
    note: str | None = None,
) -> None:
    """Insert (or replace the same key/scope/as_of) one sourced assumption."""
    validate_assumption(key, scope, source_url, source_title)
    stmt = (
        pg_insert(ValuationAssumption)
        .values(
            id=uuid.uuid4(),
            methodology_version=VALUATION_METHODOLOGY_VERSION,
            key=key,
            scope=scope,
            value=value,
            source_url=source_url,
            source_title=source_title.strip(),
            as_of=as_of,
            note=note,
        )
        .on_conflict_do_update(
            constraint="uq_valuation_assumption",
            set_={
                "value": value,
                "source_url": source_url,
                "source_title": source_title.strip(),
                "note": note,
            },
        )
    )
    await session.execute(stmt)
    await session.flush()


def main() -> int:  # pragma: no cover - CLI wrapper
    parser = argparse.ArgumentParser(description="Sourced valuation assumptions")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("set")
    s.add_argument("--key", required=True, choices=ASSUMPTION_KEYS)
    s.add_argument("--scope", required=True)
    s.add_argument("--value", required=True)
    s.add_argument("--source-url", required=True)
    s.add_argument("--source-title", required=True)
    s.add_argument("--as-of", required=True, type=date.fromisoformat)
    s.add_argument("--note")
    s.add_argument("--no-recompute", action="store_true")
    sub.add_parser("list")
    args = parser.parse_args()

    async def _run() -> int:
        from app.db.session import async_session_factory
        from app.models.market import Company

        async with async_session_factory() as session:
            if args.command == "list":
                rows = (
                    await session.execute(
                        select(ValuationAssumption).order_by(
                            ValuationAssumption.key, ValuationAssumption.scope,
                            ValuationAssumption.as_of,
                        )
                    )
                ).scalars().all()
                for r in rows:
                    print(
                        f"{r.methodology_version} {r.key} {r.scope} {r.value} "
                        f"as_of {r.as_of} {r.source_url} ({r.source_title})"
                    )
                if not rows:
                    print("No sourced valuation assumptions recorded.")
                return 0
            try:
                value = Decimal(args.value)
            except InvalidOperation:
                print(f"--value {args.value!r} is not a number")
                return 2
            try:
                await record_assumption(
                    session, key=args.key, scope=args.scope, value=value,
                    source_url=args.source_url, source_title=args.source_title,
                    as_of=args.as_of, note=args.note,
                )
            except ValueError as exc:
                print(str(exc))
                return 2
            await session.commit()
            ids = list((await session.execute(select(Company.id))).scalars().all())
        print(f"Recorded {args.key} ({args.scope}) = {value} as of {args.as_of}.")
        if not args.no_recompute:
            from app.services.recompute import Engine, Trigger, recompute_many

            report = await recompute_many(
                ids, Trigger.ASSUMPTIONS,
                engines={Engine.FAIR_VALUE, Engine.SCORE, Engine.THESIS},
            )
            print(report.summary())
        return 0

    return asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
