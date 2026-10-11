# Phase 8 Continuous-Intelligence research (roadmap §17, §23, §24 — watchlist, alerts, thesis invalidation triggers on new data arrival, event bus / audit ledger)

**DATA WARNING: outputs computed on synthetic data — not for real-money use until Phase 13 ships** (per CONTRACT.md standing pre-phase gate; all data is synthetic until Phase 13).

**Researcher:** Nadia (competitor analyst) · **Research date:** 2026-10-11 (all new fetches; prior-file items reused per brief, marked REUSED)
**Questions:** (1) How Koyfin / Simply Wall St / Alpha Spread structure user watchlists (tags, columns, multi-list) and alert triggers (price targets, valuation changes, earnings releases, restatements, thesis-condition violations). (2) Thesis-invalidation automation patterns — evaluating stored Phase 5 invalidation thresholds against incoming Phase 7 parsed facts and Phase 1 daily prices without false positives. (3) Audit-log / event-history patterns for investment apps.
**Method:** web search + page fetches only. No code touched, no files written. Unverifiable = `no data` with one-line note.
**Context:** existing backend has Phase 5 theses with stored invalidation conditions + ledger, Phase 7 document parse pipeline with provenance, Phase 1 data-quality + refresh/assess job. Research informs watchlist/alert/trigger architecture against those.

Prior files reused, not re-researched: `.workflow/research/phase-5-investment-thesis.md` (2026-10-10), `.workflow/research/phase-7-document-intelligence.md` (2026-10-11), `.workflow/research/app-wide-ux-patterns.md` (2026-10-09).

Roadmap mapping used: Phase 8 = §17 (watchlist), §23 (alerts), §24 (thesis invalidation triggers on new data arrival) + event bus / audit ledger. The brief adds "event bus / audit ledger" as the cross-cutting substrate.

---

## 1. How competitors structure watchlists (multi-list, columns, groups/tags)

### 1a. Koyfin — the structural template to copy (dozens of lists, reusable views, groups, summary rows, custom formula columns)

- **Dozens of custom watchlists across all asset categories, each tailored with specific data points:** https://www.koyfin.com/features/watchlists (fetched 2026-10-11).
- **Multi-list mechanics:** "New" button creates a list; reorder by dragging tabs; rename / duplicate / share / delete per list; add tickers via "Add Ticker"; bulk import by copy-paste into Import Securities pop-up; right-click a security to load it into Snapshot/Graph or delete it: https://www.koyfin.com/help/mywatchlists/ (fetched 2026-10-11).
- **Columns:** free column choice per watchlist, auto-saved; right-click header to rename / sort / remove; drag borders to resize; **Watchlist Views** save a column+table-settings configuration and reuse it across watchlists and dashboard watchlist widgets: https://www.koyfin.com/help/mywatchlists/ and https://www.koyfin.com/features/watchlists (both fetched 2026-10-11).
- **Groups (the tags equivalent — no free-text tags observed):** group by predefined Sector/Country; custom groups by typing `*Name` in Add Ticker (e.g. `*Longs`) or the "+New Group" button: https://www.koyfin.com/help/mywatchlists/ (fetched 2026-10-11). Free-text per-symbol tags: `no data` — no tag UI observed on any fetched Koyfin page 2026-10-11.
- **Summary rows + notes + sorting:** per-table summary statistics (average, max, min, percentiles) at the bottom, per-group when grouped; manual drag sort, header sort, and multi-variable advanced sort; "group instruments as desired, add summary rows or notes": https://www.koyfin.com/help/mywatchlists/ and https://www.koyfin.com/features/watchlists (both fetched 2026-10-11).
- **Custom formula columns:** user-defined math on existing series added as watchlist columns: https://www.koyfin.com/features/watchlists and https://www.koyfin.com/help/mywatchlists/ (both fetched 2026-10-11; full formula syntax lives at https://www.koyfin.com/help/custom-formulas/, not fetched in this pass).
- **Sharing + dashboard embedding:** one-click watchlist sharing with other Koyfin users for a common workspace; any watchlist can be added to a custom dashboard alongside chart/benchmark/news widgets that update together: https://www.koyfin.com/features/watchlists (fetched 2026-10-11). REUSED app-wide-ux §2.1: linked-widget dashboards crowd risk ("feels crowded when too many widgets are loaded") — keep v1 to watchlist + one detail surface.
- **Watchlist News:** real-time streaming articles / press releases / filings / transcripts scoped to the list: https://www.koyfin.com/help/mywatchlists/ (fetched 2026-10-11).
- **My Koyfin IA precedent:** user-created artefacts (watchlists, dashboards, templates) collected under one "My Koyfin" nav section, collapsible/reorderable with favourites: REUSED app-wide-ux §1.1 https://www.koyfin.com/help/release-notes/customizable-left-navigation/ (retrieved 2026-10-09).

### 1b. Alpha Spread — tiered multi-list with journal attached, column detail ungated-unknown

- **List counts per tier (citable capacity planning input):** Free 1 watchlist × 30 stocks; Premium 5 × 50; Unlimited 20 × 1000: https://www.alphaspread.com/service-pricing (fetched 2026-10-11).
- **Investment Journal on all tiers** ("see what worked and what didn't" — thesis-adjacent note-taking next to the list, same page table): same URL (fetched 2026-10-11).
- **Watchlist columns / tags / groups on Alpha Spread:** `no data` — pricing and dashboard pages expose no column-picker, grouping, or tagging UI in this pass (dashboard pages are login-walled: https://www.alphaspread.com/dashboard/watchlists fetched 2026-10-11 returned shell only).
- **Third-party corroboration of the alert-adjacent value:** "set alerts for when a stock's price drops to or below its calculated intrinsic value… genuinely useful for patient value investors": https://completetradersedge.com/alphaspread-review/ (fetched 2026-10-11; REUSED Phase-5 §3 pattern).

### 1c. Simply Wall St — feed-first, not table-first (Dashboard + Watchlist + Portfolio + Important Update emails)

- **The monitoring triple:** Dashboard (investment newsfeed of every update on portfolio/watchlist names) + Watchlist (right-hand updates rail while reviewing) + Important Update emails (opt-in under Notifications, with added context/analysis per event): https://support.simplywall.st/hc/en-us/articles/7246565363471-How-to-Monitor-Your-Stocks-and-Discover-New-Investing-Ideas (fetched 2026-10-11; REUSED Phase-5 §1, Phase-7 §3a).
- **Feed content:** earnings-report insights, insider selling analysis, upcoming dividends, news events, in-depth articles — the reader's job is explicit: "look for any developments that potentially validate or invalidate your existing narrative": same URL (fetched 2026-10-11).
- **SWS multi-list / columns / tags:** `no data` — no multi-watchlist, column configuration, or tagging UI observed on any fetched SWS page 2026-10-11. SWS competes on the event feed (REUSED app-wide-ux §2.1: the feed became "the largest single predictor of paid user retention"), not on table power.
- **Sell discipline surfaced in the same feed (the §24 UX to copy):** 3-question checklist — narrative changed for the worse? conviction lost? overvalued vs own fair value? — Yes×3 = sell; valuation-only Yes = sell on price; conviction-only Yes = trim: same URL (fetched 2026-10-11; REUSED Phase-5 §1).

### 1d. Watchlist-structure synthesis (what §17 owns that no single competitor covers)

No competitor combines Koyfin's table power (multi-list + reusable views + groups + custom columns) with SWS's narrative-tied feed and Alpha Spread's per-list journal. Tags specifically are the gap: Koyfin has `*Groups`, SWS/Alpha Spread show nothing tag-like — a `watchlist → entries → {symbol, group, note, thesis_link}` shape with groups-as-tags has no exact incumbent.

---

## 2. Alert triggers: price targets, valuation changes, earnings, restatements, thesis violations

### 2a. Koyfin Desktop Alerts — the trigger taxonomy to copy (price / valuation / technical / documents, per-symbol AND per-watchlist)

- **Four alert families:** Price; Valuation; Technical indicators; Documents (press releases, news, earnings transcripts, filings): https://www.koyfin.com/help/release-notes/v3-66-desktop-alerts/ (fetched 2026-10-11).
- **Document alerts are toggle-only** (no threshold setup); price/technical/valuation alerts open a setup screen (type + conditions + frequency + optional notes): same URL (fetched 2026-10-11).
- **Watchlist-level alerts:** one window for the whole list — document toggles apply to *all tickers in the list*: same URL (fetched 2026-10-11). Per-watchlist numeric (price/valuation) alert: `no data` — only document-type toggles documented at list scope.
- **Portfolio alerts:** per-security document alerts inside My Portfolio / Model / Client Portfolio: same URL (fetched 2026-10-11).
- **Instrument coverage is tiered by data availability (honest-degradation precedent for EGX):** global stocks get all four families; US ETFs lose document alerts; non-US ETFs and mutual funds keep price+technicals only: same URL (fetched 2026-10-11).
- **Quotas:** Free 5 alerts; Plus 50; Premium 500 (incl. watchlist + portfolio alerts); Advisor Core/Pro add Model/Client portfolio scope: same URL (fetched 2026-10-11).
- **Delivery:** desktop bell (right-sidebar Notifications panel, click-through to source section) + email + mobile push; per-method toggles in Notification Settings; global kill-switch pauses everything: same URL (fetched 2026-10-11).
- **Management:** Alerts Center with My Alerts tab (search by ticker; filter by Documents/Price/Technical/Valuation; sort by modified/ticker/category; edit/stop/delete per alert) + bell-counter of active alerts per ticker in tables: same URL (fetched 2026-10-11).
- **Marketing-page corroboration:** "alerts for any security… price moves, technical signals, valuation changes, or news… news alerts for the entire watchlist at once": https://www.koyfin.com/features/watchlists (fetched 2026-10-11).

### 2b. Alpha Spread — valuation-led alerts + weekly screener digest + price targets

- **Watchlist Alerts ("targeted alerts… about your companies") and Price Alerts & Reminders ("customize your alerts and let Alpha Spread watch the market for you") ticked on all three tiers:** https://www.alphaspread.com/service-pricing (fetched 2026-10-11).
- **Valuation-crossing alert:** "notified when price falls to intrinsic value or below it with a margin of safety": https://www.alphaspread.com/ (fetched 2026-10-11; REUSED Phase-5 §3 range frame).
- **Price Targets page:** user-set target per watched stock from own model or manual; email on hit: https://www.alphaspread.com/dashboard/price-targets (fetched 2026-10-11 via search excerpt; page shell is login-walled).
- **Screener Alerts (Unlimited tier only):** weekly email of *new stocks matching saved screener criteria*: https://www.alphaspread.com/service-pricing (fetched 2026-10-11).
- **Per-company numeric guardrail on filed accounts (e.g. "email me when margin breaks X on the next filing"):** `no data` — not stated on pricing or review pages; third-party comparison explicitly records this as "not established rather than absent": https://valuescreener.ai/compare/alpha-spread (fetched 2026-10-11 via search excerpt).
- **Earnings-release / restatement / thesis-violation alert types on Alpha Spread:** `no data` — none observed 2026-10-11.

### 2c. SWS Important Updates — earnings/dividends/valuation/insider/news, thesis-framed

- **Same feed triple as §1c** (Dashboard + Watchlist rail + email) carries earnings, dividends, valuation changes, insider selling, news with validate-or-invalidate instruction + 3-question sell checklist: https://support.simplywall.st/hc/en-us/articles/7246565363471-How-to-Monitor-Your-Stocks-and-Discover-New-Investing-Ideas (fetched 2026-10-11).
- **Per-user numeric thresholds (price target, ratio floor) on SWS:** `no data` — updates are editorial/event-driven, not user-parameterised rules.
- **Restatement-specific SWS alert:** `no data` — REUSED Phase-7 §3a: no per-line-item revision table or restatement flag observed.

### 2d. Restatement detection as alert infrastructure (US-shaped; EGX has no equivalent feed — §24 must build its own detector)

- **Arche versioned-statement pattern (the §24 restatement-detector spec):** restatement adds a version, never overwrites; per-metric old/new/delta computed; materiality classified; `as_reported=true` (as originally stated) vs `as_of_date` (knowable on date) as separate parameters; empty timeline with severity NONE means "no restatement", not missing data; `restatement.detected` webhook carries metric, change_type, old/new/delta, materiality (worked AXON example: $680.289M convertible-notes reclassification, CRITICAL): https://arche.fi/use-cases/restatement-analysis (fetched 2026-10-11).
- **Distill Markets revisions API (corroborating shape + caveat):** revisions endpoint lists annual facts changed between earliest-held and latest filing with both values, both EDGAR accessions, relative change, and changeType (entity-change / multi-period-recast / amendment / unclassified); public 60-day feed rebuilds nightly; **changed ≠ restated** — most flagged changes are re-presentations (spin-off, new standard, entity change), unclassified rows are the investigate-shortlist; detail capped at 100 rows by |relative change|: https://www.distillmarkets.com/restatements-api (fetched 2026-10-11).
- **EGX restatement feed / non-reliance equivalent:** `no data` — REUSED Phase-7 §3d (no XBRL instance, restatement taxonomy, or 8-K-Item-4.02 equivalent). §24 restatement detection therefore runs on Phase 7 parsed facts: same-period-different-value across two bulletin PDFs = candidate revision, with EAS-gotcha tags (REUSED Phase-7 §2c) as confounders to exclude before firing.
- **Thesis-condition-violation alerts on any of Koyfin/SWS/Alpha Spread (user's stored fundamental rule evaluated on new filing, e.g. ThesisCheck-style):** `no data` — none observed on any fetched page 2026-10-11. This is the §24 gap the product owns (see §3 for the non-incumbent patterns that fill it).

---

## 3. Thesis-invalidation automation: evaluate stored Phase 5 thresholds against Phase 7 facts + Phase 1 prices without false positives

No incumbent does this end-to-end. The citable pieces come from adjacent products and open-source specs; each is labelled for what it contributes to the false-positive problem.

### 3a. ThesisCheck.ai — the closest shipped product (user hurdles × statutory filings, Passed/Breached, page-cited)

- **Contract:** user defines 2–3 catalyst hurdles per ticker (e.g. gross margin >35%, cloud growth >30%, debt reduction); engine fetches the official 10-Q/10-K the second it hits EDGAR, parses statements + segments + footnotes, marks each catalyst **Passed or Breached** with exact page/table citations, delivers an inbox briefing before market open: https://thesischeckai.com/ (fetched 2026-10-11).
- **Threshold-sensitivity demo:** the verdict score (worked GOOGL 8.8/10, 3/3 met) visibly shifts as the user drags hurdle presets (Balanced/Strict/Skeptical/Bear) — i.e. thresholds are first-class inputs, not hidden: same URL (fetched 2026-10-11).
- **Deterministic-forensic positioning** ("not a conversational chatbot"; flat subscription, no per-prompt metering; primary-sources-only): same URL (fetched 2026-10-11). Independent verification of the determinism claim: `no data` — marketing copy, no methodology whitepaper retrieved in this pass.
- **EGX applicability caveat:** SEC-EDGAR-only sourcing; no EGX/PDF-Arabic pipeline claimed: same URL (fetched 2026-10-11). For EGX the "second it drops" trigger maps to the EGX bulletin + Phase 7 parse, with filing-lag + extraction-confidence attached (REUSED Phase-5 §5).

### 3b. AgenticThesis (open-source, PyPI v0.7.0) — the evaluation-state machine to copy

- **Four stored outcomes per claim:** `supported` / `weakened` / `possibly_invalidated` / `unknown`, with "Not enough evidence" as an explicit verdict instead of forcing an answer: https://pypi.org/project/agentic-thesis/0.7.0/ (fetched 2026-10-11 via search excerpt).
- **Human-review gate:** new filing → per-reason comparison with source quotes → proposed `ThesisDelta` → user approves → immutable `ThesisSnapshot` vN+1; stale approvals rejected with `version_conflict` (compare-and-swap): same URL (fetched 2026-10-11).
- **Cost/false-positive control:** daily SEC check; no new filing → record the check and stop (no LLM run); new filing → RAG + analysis only then: same URL (fetched 2026-10-11). Directly applicable to §24: evaluate triggers only on (a) new Phase 7 fact batch for a covered symbol, or (b) Phase 1 daily price crossing a price-side threshold — never on a timer alone.
- **License/integration detail:** `no data` — did not fetch the repo or license file in this pass.

### 3c. Equity-research-update skill — the three-test + killing-conditions discipline (manual-trigger precedent)

- **Three-test per update:** pillars (SILENT/CONFIRMED/INVALIDATED) × killing conditions (fired/not) × load-bearing magnitude shift; result mechanically maps to action classes Log-only / Refined / Heavy refinement / Direction reversal: https://github.com/GeniusTrader-Harry/equity-research-update-skill (fetched 2026-10-11 via search excerpt).
- **Sacred rules to copy into §24:** killing conditions are never quietly downgraded (a fired KC forces ≥ Heavy refinement); never invent a new pillar via an update (rebuild instead); Appendix C update-history table = human-readable audit trail inside the memo: same URL (fetched 2026-10-11).
- **Gap it names honestly:** "NOT an automated monitoring tool. Trigger is manual — no cron, no webhook." §24 is the automation of exactly this workflow: same URL (fetched 2026-10-11).

### 3d. Thesis-tracker skill spec — the threshold/ledger schema to copy (confirm/warning/break + reconciliation)

- **Per-pillar row:** falsifiable claim + baseline w/ as-of + expected path + **confirm / warning / break thresholds each with provenance label** + latest-evidence ledger id + signal + evidence quality + approval provenance (inherited/draft/approved) + next proof point (dated release/event) + owner: https://tool.lu/skill/s/nJz (fetched 2026-10-11 via search excerpt).
- **Status lattice:** strengthening / intact / watch / impaired / broken / changed / untested / retired; aggregate follows core pillars (1 impaired ⇒ aggregate ≥ watch; 2+ impaired ⇒ impaired; core broken/changed propagates): same URL (fetched 2026-10-11).
- **Anti-drift rules:** append-only ledger (superseded/stale marked, never edited); drift patterns named per update (reason-changed, catalyst-laundering, valuation-substitution, dismissal-by-horizon, protection-as-reason); ungettable comparisons marked `n/a` with reason, never column-dropped: same URL (fetched 2026-10-11).
- **Company-thesis vs security-call split:** business verdict and actionability tracked separately; without price + valuation frame + position context the call is `inputs missing` naming the missing input: same URL (fetched 2026-10-11). Matches AGENTS.md rules 9–10 (trigger forces reassessment, never auto-sells).

### 3e. Deterministic red-flag rules (Midas Edge) — the no-LLM tripwire layer

- **Pattern-matching + NLP over 8-K/10-K/10-Q/NT filings for disclosure events** (going-concern, liquidity, auditor, legal, executive transitions, accounting incl. restatement-high via 8-K Item 4.02), each with severity feeding an attention queue; critical = immediate alert; rule coverage validated against a committed 40-excerpt real-SEC corpus with conformance tests: https://midas-edge.com/methodology/red-flags (fetched 2026-10-11 via search excerpt).
- **EGX mapping:** rule layer ports to EGX bulletin forms (board/AGM resolutions, auditor report qualifications, capital-increase reports — REUSED Phase-5 §5 continuing obligations) as keyword + template rules evaluated on Phase 7 parsed text before any LLM step.

### 3f. False-positive guardrails (synthesis — every mechanism cited above)

1. **Evaluate on arrival, not on schedule** (AgenticThesis §3b): trigger evaluation runs when Phase 7 lands a new fact batch or Phase 1 lands a price crossing; a quiet day writes a "checked, nothing new" ledger row, not an evaluation.
2. **Three-level thresholds** (tracker §3d): warn ≠ break. Warning touches set `watch` + next-proof-point; only break-level crossings propose invalidation. Single-quarter blips on TTM-metric thresholds should not fire (REUSED Phase-7 §3a: SWS TTM presentation exists precisely to smooth quarterly noise).
3. **Evidence-quality gate** (tracker §3d + Phase-7 provenance): a break computed from a low-confidence parse (Camelot accuracy below floor, scanned-PDF OCR path, EAS-ambiguous line) yields `unknown`/needs-review, never `broken`. Store extraction confidence per check (REUSED Phase-5 §5, Phase-7 §4).
4. **Restatement-vs-new-evidence disambiguation** (Arche/Distill §2d): same-period value change across filings = revision candidate → re-evaluate affected checks against the version chain and log a restatement event; do not count it as fresh-period deterioration.
5. **As-reported vs as-knowable discipline** (Arche §2d): backtest/replay of trigger logic must use as-reported vintages (look-ahead-bias bar REUSED Phase-5 §3 Alpha Spread backtest).
6. **Human-review gate for invalidation, auto-delivery for warnings** (AgenticThesis §3b + ThesisCheck §3a): warnings may notify immediately; `broken`/KC-fired proposals wait for user confirm and land as new ledger versions (compare-and-swap; REUSED Phase-5 §1 SWS 24h-edit-then-view-only precedent for timeline immutability).
7. **Missing-data fail-closed** (open-source monitor-center precedent): evaluators "never silently pass when required data is missing" — emit a persisted trigger record with missing-data reason instead: https://github.com/ZhuLinsen/daily_stock_analysis/issues/2281 (fetched 2026-10-11 via search excerpt).

---

## 4. Audit log / event-history patterns (the event-bus / audit-ledger substrate)

### 4a. Retail-investment audit card (alphactor.ai) — the §24 ledger UX to copy

- **Logged per event:** timestamp to the second (portfolio canonical timezone) + actor (user or system process) + event type (trade, rebalance, alert triggered, note added, compliance rule flagged, webhook fired…) + affected positions (tickers+sizes) + free-text description: https://alphactor.ai/blog/portfolio-audit-trail-compliance (fetched 2026-10-11).
- **Query + export:** filter by date range / event type / ticker; CSV export (regulator/LP) + JSON (archival pipeline): same URL (fetched 2026-10-11).
- **Hygiene rules:** rule-triggered events auto-log (never manual capture); notes linked to trades contemporaneously (30-second note beats 30-minute reconstruction); compliance sub-log reviewed weekly; monthly CSV snapshots to cold storage (S3 object-lock / write-once) for immutability; log inaction and overrides explicitly (skipped adds, held exits); log rule changes themselves as events (actor, timestamp, before/after, rationale) so old flags stay interpretable: same URL (fetched 2026-10-11).
- **Append-only in spirit:** corrections are new entries referencing the old, never mutations: same URL (fetched 2026-10-11).

### 4b. Engineered event streams (compliance-grade precedents)

- **NexusTrade event taxonomy:** every tick evaluation emits typed events — signals (conditions triggered), orders, guards (blocked trades with reason), audits (batched constraint-check rows explaining skips/modifications), plus Market snapshots and PriceAnomaly diagnostics (>5× tick-to-tick move with split/adjustment attribution state): https://nexustrade.io/docs/features/event-types (fetched 2026-10-11 via search excerpt).
- **QuantFolio/Deep Alpha audit log:** secure-by-default, non-disableable; per event: UTC datetime, tenant, application, access method (API key/authenticated/anonymous), user/investor/session ids, action, info, status OK/Error; tracked actions enumerated (portfolio generation, advice updates, forecast calculation, document upload, settings changes): https://docs.quantfol.io/audit-log (fetched 2026-10-11 via search excerpt).
- **Passive.cloud immutable-trail architecture:** append-only event stream as canonical evidence (drift detected → rebalance proposed → policy checked → trade generated → approved → sent → confirmed → reconciled); canonical JSON + KMS signatures; Merkle-tree daily bundles anchored in WORM + independent secondary copy; model/ruleset/deployment versions in event metadata; retrieval drills as acceptance test: https://passive.cloud/immutable-audit-trails-for-automated-portfolio-changes-archi (fetched 2026-10-11 via search excerpt).
- **Winzinvest 4-layer audit trail:** (1) execution fills; (2) intent logs (pre-order intent + post-fill result, crash-safe linkage); (3) regime + gate logs (every classification and per-candidate reject with reason — including rejected candidates); (4) override/exception logs (who/when/why, the layer examiners care about most): https://www.winzinvest.com/guides/systematic-trading-audit-trail-sec (fetched 2026-10-11 via search excerpt). Copyable: §24 logs rejected/inapplicable evaluations (gate log), not just firings.
- **TradeMemory hash-chained records:** SHA256 data_hash per decision record, prev_hash chain verificaton, daily Merkle roots for day-level proof without re-walking: https://glama.ai/mcp/servers/mnemox-ai/tradememory-protocol/schema (fetched 2026-10-11 via search excerpt). Hash-chaining is likely overkill for v1; the takeaway is versioned + tamper-evident intent (cold-storage snapshots per §4a suffice).

### 4c. What the §24 ledger therefore records (synthesis, all elements cited above)

`event {ts, actor (user/system + rule version), type (watchlist.add/remove, alert.created/fired/acked, fact.landed, check.evaluated {pass/warn/break/unknown}, restatement.detected, thesis.updated, rule.changed, note.added), symbols, inputs_snapshot (fact ids + price as-of + methodology version), reason, supersedes}` — append-only, filterable by symbol/type/date, exportable. No competitor publishes this full shape for PDF-sourced EGX facts (REUSED Phase-7 §4: SWS/Koyfin/Alpha Spread provenance stops at source footers without page/cell locators).

---

## 5. EGX + existing-backend mapping (builds on prior files, not repeated)

- **Watchlist (§17) SUPPORTED by existing backend inputs:** Phase 1 daily prices + data-quality flags feed per-row price/change/as-of/staleness badges (REUSED app-wide-ux §6.1: as-of + delay badge + source line; never blank stale cells); Phase 4 scores + Phase 6 Shariah states feed per-row verdict/grade columns (REUSED app-wide-ux §8: two-part verdict + ratio-vs-threshold + report date); Phase 5 theses link per-row journal/narrative (Alpha Spread Investment-Journal precedent §1b). Koyfin's tiered instrument coverage (§2a) is the precedent for honest EGX degradation (thin-consensus names show history-anchored ranges + INSUFFICIENT_DATA, REUSED Phase-5 §5).
- **Alerts (§23) PARTIALLY SUPPORTED:** price-side triggers computable from Phase 1 refresh/assess job (crossings, valuation-vs-price gaps from Phase 3/4 outputs); document-side triggers computable from Phase 7 landing events (new bulletin parsed for a watched symbol ≈ Koyfin document alert §2a); valuation-change alerts need versioned score history (Phase 4) with the ±5% neutral band discipline (REUSED Phase-5 §3). Restatement alerts need the §2d detector built on Phase 7 versions — no native feed exists.
- **Invalidation triggers (§24) SUPPORTED as filing-anchored checks with stored confidence:** every Phase 5 invalidation condition (metric + threshold + period + evidence source + pre-committed action, REUSED Phase-5 §6 steer 3) maps to a mandated EGX disclosure (REUSED Phase-5 §5 continuing obligations); evaluation inherits filing-lag + extraction-confidence, stored per check (Phase-7 provenance shape: page/bbox/table/row/col + engine + accuracy + accounting_basis, REUSED Phase-5 §5, Phase-7 §4). Price-side conditions map to Phase 1 closes with as-of + staleness.
- **Event bus / audit ledger:** no existing bus described in the brief beyond the three jobs; §4c is the greenfield schema. The Phase 5 ledger (REUSED Phase-5 §1 Narrative Updates timeline) becomes one event stream among several (facts landed, checks evaluated, alerts fired, rules changed).
- **EGX catalyst/earnings surfaces for trigger wedding:** Decypha calendar + egypt-stocks tracker + AskBorsa results page seed dated catalyst records (REUSED Phase-5 §4); Confirmed-vs-Tentative labelling and impact scoring remain `no data` (carried over).

---

## 6. `no data` log (do not re-search blindly)

- Koyfin free-text per-symbol tags; per-watchlist numeric (price/valuation) alerts; Koyfin EGX-name alert/Actuals pages.
- SWS multi-watchlist / column config / tagging UI; SWS user-parameterised numeric thresholds; SWS restatement flag or per-line-item revision table.
- Alpha Spread watchlist column/group/tag UI (pages login-walled); per-company filed-account guardrail alerts (explicitly "not established" per valuescreener.ai); Alpha Spread earnings/restatement/thesis-violation alert types; Alpha Spread EGX pages.
- EGX restatement feed / non-reliance equivalent; EGX confirmed-vs-tentative event dating; EGX company guidance calendars; impact-scored EGX catalyst feed (all carried over Phase-5 §6 / Phase-7 §5).
- AgenticThesis repo license/integration detail; ThesisCheck determinism whitepaper (marketing claim only in this pass).
- Any stored-thesis-threshold alert shipped by Koyfin/SWS/Alpha Spread (none observed — the §24 gap).
- Scanned-vs-digital share of EGX PDFs; OCR accuracy on Arabic-Indic numerals (carried over Phase-7 §5).

---

**Design steers for PM (non-binding, from evidence):** (1) §17 watchlist = Koyfin table mechanics (multi-list + reusable column views + `*Groups` + summary rows + custom formula columns + sharing) with SWS's updates rail per list and Alpha Spread's per-list journal; groups serve as tags v1. (2) §23 alerts = Koyfin's four families (price/valuation/technical→score-change/documents) with per-symbol setup + per-watchlist document toggles, Alpha Spread's valuation-crossing + weekly-screener-digest emails, SWS's validate-or-invalidate framing on every notification; quotas per tier (5/50/500 precedent). (3) §24 triggers = ThesisCheck contract (user hurdles × new filings, Passed/Breached + page citations) evaluated on arrival only, AgenticThesis state machine (supported/weakened/possibly_invalidated/unknown + human-review gate + version_conflict), tracker three-level thresholds (warn→watch, break→reassessment-proposal, never auto-sell), Arche/Distill restatement detector (version-not-overwrite, deltas, materiality, as-reported vs as-knowable), Midas-Edge deterministic tripwire layer before any LLM step, fail-closed on missing data. (4) Ledger = alphactor card shape (ts/actor/type/positions/description + filters + CSV/JSON export + cold-storage snapshots) over NexusTrade-typed events (signals/guards/audits/anomalies) with Winzinvest's four layers (intent/regime-gate/override incl. rejected evaluations) — append-only, rule-changes logged as events. The combination — versioned, filing-cited, machine-checkable watchlist/alert/trigger/ledger loop on PDF-sourced EGX facts — has no incumbent.
