# R22 — Phase 2 scope (Industry Intelligence + positioning)

**From:** Nour (pm) · 2026-10-10
**Source:** `.workflow/research/phase-2-industry-competitive-landscape.md` + roadmap §2–§3 exit criteria.
**Binding:** AGENTS.md rules 2/3/5 + INSUFFICIENT_DATA pattern; cross-phase contracts (one migration, UUID PKs, `/api/<domain>/companies/{id}`, `methodology_version` on every score).

## BUILD (in order, must-have first)

**R1. GICS 4-level tables + EGX 18-sector mapping layer (canonical = GICS).**
Tables `sectors → industry_groups → industries → sub_industries` mirroring GICS codes/names (11/25/74/163); EGX 18-sector list stored as a separate mapping table, never the PK. Every mapping row carries `source_id` (EGX URL) + `as_of`.
*Accept: GICS code lookup returns 4 levels; EGX sector resolves to ≥1 GICS node with source+date.*

**R2. EGX sector backfill of `companies.sector/industry` (one-shot, ISIN join).**
Backfill from EGX listed-stocks/sector pages, joined on ISIN (Reuters `.CA` secondary only); free-text columns stay, FKs added. No scheduler in Phase 2.
*Accept: backfill script updates N companies from EGX rows, each traceable to page URL + date, zero fabricated sectors.*

**R3. Peer groups: default + editable override.**
Default peers = same EGX sector (fallback: same GICS sub-industry); user-edited peer list persisted per company (override table, versioned). Copy SWS "Edit Peers" pattern, not Finviz paywall.
*Accept: GET returns default peers; PUT override persists and subsequent GET uses it.*

**R4. Versioned `industry_metric_profiles` (seed 3 + default only).**
Schema `(industry_id, metric_key, display_order, methodology_version)`; seed banks / real estate / industrials + one default profile. All later phases read the profile id + version.
*Accept: banks profile exposes bank metrics, other industries fall back to default, version echoed in API.*

**R5. Honest peer percentiles + written explanation.**
Percentile computed per metric over peers-with-data only; response includes `N_peers, N_with_data, profile_id, methodology_version, as_of`; returns `{"value": null, "status": "INSUFFICIENT_DATA"}` when below minimum-N (never ranks 1-of-1); human-readable explanation string per metric.
*Accept: 1-peer universe returns INSUFFICIENT_DATA, multi-peer returns percentile + explanation with counts.*

**R6. One migration + one domain API (`011_industry`).**
Single migration `011`, UUID PKs, `ix_/uq_` names, explicit `ondelete`; one router `GET /api/industry/companies/{id}` (peers + percentiles + profile version), hand-serialized Decimals/dates per contract.
*Accept: migrate up/down round-trips; route 404s unknown company; payload carries methodology_version.*

## CUT / DEFER (with reason)

- **Continuous EGX re-scrape scheduler → defer to Phase 7/8.** Ops surface with no exit-criteria payoff.
- **Full 74-industry metric profiles → cut to 3+default.** Seeding all industries invents metrics with no data (violates rule 2). Expand in Phase 3 per valuation need.
- **Saved screener presets / custom formulas / dashboards → defer to Phase 10.** Exit criteria ask for peer comparison, not a terminal.
- **EGX33 reconciliation + purification math → Phase 6 Shariah.** Thresholds beyond AGBI summary are `no data` — citing them now fabricates methodology.
- **Real-time prices/alerts, US breadth, execution/custody, AI stock-picking chatbot → never build.** Owned by incumbents; execution forbidden by rule 9, chatbot by rules 6/10.

## Standing positioning for Phases 3–10 (no prices set)

- **Standing req 1 (Ph 6):** versioned Shariah verdict — every verdict pins `methodology_version + report_date + per-rule UNKNOWN`.
- **Standing req 2 (done in Ph 2, reused):** dual GICS×EGX taxonomy with provenance on every row.
- **Standing req 3 (Ph 3–4):** per-industry metric profiles + honest percentiles feed valuation model choice and investment-score confidence.
- **Standing req 4 (all phases):** data-quality as product — quality score + `as_of/last_synced_at` on every company page, screener, verdict; `null` when unassessed, never a default.
- **Standing req 5 (Ph 6):** EGX dividend purification math in EGP tied to cited filings.
- **Pricing lanes (B0 umbrella only):** free tier vs EGX-only research seat under SWS-$131/yr / Musaffa-$200/yr / Decypha-$600/yr umbrella vs broker per-trade lane — actual pricing decided post-Phase 10.
