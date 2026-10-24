# R45 — Owner review of R43 design, R44 methodology and the UI spec (user, 2026-10-24)

Under the new "Owner decisions" rule (CONTRACT.md), the user reviewed the choices already baked into the paused work.

## Architecture (R43 design `.workflow/design/r43-computed-company-data.md`) — all approved as designed
| # | Decision | Answer |
|---|---|---|
| A1 | Engine fundamentals source | Statement lines only (D-1); FinancialFact stops feeding engines |
| A2 | Auto-compute mechanism | Inline + fingerprint staleness table `company_compute_state` (D-4); no queue, no scheduler |
| A3 | Caller-input POST routes (§3.2) | Removed (D-5) |
| A4 | `/admin` protection | Same shared API token; grouping only |

## Methodology (R44) — approved
| # | Decision | Answer |
|---|---|---|
| M1 | Valuation assumptions v1 | Discount 28.36% (3y EGP T-bond 24.128% + mature ERP 4.23%), terminal growth 5.4%; relative multiples INSUFFICIENT until sourced |
| M2 | Shariah activity classification | Per-company activity tags; Islamic-bank exceptions; 13 sectors default permitted; mixed sectors UNKNOWN until reviewed |

## UX (UI spec `.workflow/design/ui-redesign-2026-10.md`)
| # | Decision | Answer |
|---|---|---|
| U1 | Visual direction | **Changed: "Friendly retail app"** — rounded cards, larger type, more whitespace (Thndr/Robinhood feel). Replaces spec §2 tokens and the dense look in §3/§4. |
| U2 | Navigation | Left sidebar (3 groups) + mobile top bar/drawer — as spec |
| U3 | Company page | 7 tabs — as spec |
| U4 | Stance wording | Leans buy / Neutral / Leans reduce + Not assessed — as spec §5.1 |
| U5 | Recommendations vs Momentum rankings | Keep both, distinct names (Composite vs Momentum score) — as spec |
| U6 | Stock lists | Cards on phone, friendly tables on desktop (sortable) |

## Consequences
- ux-expert revises spec §2 (tokens: palette, type scale, radius, spacing, shadows) and the visual parts of §3/§4 for U1, presenting 2–3 concrete variants (palette + font + density) as `ASK USER` before anything is built.
- FE-1 structure (shell, routing, hub, admin, i18n split) stands; the re-skin lands in `styles/tokens.css`, `styles/ui.css` and `components/ui/*`, so page lanes keep their structure and translation work.
- R43 backend and R44 proceed unchanged.

## U1 follow-up (user, 2026-10-24)
Variant **A "Cobalt Cards"** from `.workflow/design/ui-friendly-direction.md` §5 (Plus Jakarta Sans + Cairo, cobalt accent, soft-shadow cards, 56 px rows; weight 700 allowed). Its tokens replace spec §2.2–2.4; its §3 component notes amend the spec.

## Analyst rulings (user, 2026-10-24; `.workflow/research/analyst-r43-2026-10-24.md`)
| # | Decision | Answer |
|---|---|---|
| M3 | ROE/ROA with no prior period | Option A: stay INSUFFICIENT_DATA (average capital only; one definition) |
| M4 | Score checks `dividend_stability` / `dividend_growing` | NOT_RUN with reason until a declared-DPS source exists; derived paid DPS used only for purification, labelled "cash dividends paid per share (derived)"; `dividend_earnings_coverage` labelled "cash paid / EPS" |
| M5 | Fair-value horizon mismatch (F15) | Fade the discount rate: R44 cost of equity (28.36%) for the explicit stage, then a sourced long-run cost of equity consistent with 5.4% terminal inflation for the terminal value. Needs a sourced long-run rate (researcher) and `VALUATION_METHODOLOGY_VERSION` bump; until sourced, fair value stays INSUFFICIENT_DATA naming the missing assumption. |

## M5 follow-up (user, 2026-10-24; `.workflow/research/long-run-cost-of-equity-2026-10.md`)
- `long_run_cost_of_equity` = **17.51%** (candidate B): long-run default-free EGP rate 7.34% (= 1.0423 × 1.054 / 1.0235 − 1; Damodaran July 2026 USD rate and US inflation, IMF 2031 Egypt CPI 5.4%) + Egypt default spread 5.97% + mature ERP 4.20%. No country risk premium (same structure as the explicit stage).
- Mature ERP refreshed to **4.20%** (Damodaran July 2026): explicit-stage cost of equity = 24.128% + 4.20% = **28.33%**.
- Both values are loaded as sourced `valuation_assumptions` rows (URLs and fetch dates from the research file), never hard-coded.

## F13 (user, 2026-10-24)
Fair-value stage-1 growth (`growth_high`) = the company's **3-year revenue CAGR**, capped at Egypt's **sourced nominal GDP growth** (IMF; new sourced assumption key). Fewer than 4 annual revenue points → INSUFFICIENT_DATA naming it. Until the cap value is loaded, the intrinsic leg is INSUFFICIENT_DATA naming the missing assumption. Router ruling (applies M5 consistently): excess-returns and DDM terminal values use `long_run_cost_of_equity` too.
- Cap value (user): **13.59%** (G1) = geometric average of IMF nominal growth 2027–2031 ((1 + real GDP growth) × (1 + CPI) − 1 per year; sources in `.workflow/research/long-run-cost-of-equity-2026-10.md` "Nominal GDP growth cap").
- Fade horizon (user): the explicit stage at the first-stage cost of equity lasts **5 years in every model** (FCFE, excess returns, DDM), matching the 2027–2031 growth cap; terminal value at `long_run_cost_of_equity`.
