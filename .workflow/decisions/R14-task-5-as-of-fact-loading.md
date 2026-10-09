# R14 — Task 5: `as_of` must bound fact/period loading, not just freshness arithmetic

**From:** tech-lead · 2026-10-09
**Inputs:** analyst review of Task 5 (commit 8746adc); live code `backend/app/dataquality/service.py`; roadmap plan lines 18–24 (Global Constraints); AGENTS.md rule 4; Task 2 ruling (plan lines 167–171) + `backend/app/metrics/period_selector.py:108–124`

## Finding (confirmed against live code)

`_assess_financial_statements` loads `FinancialPeriod` and `FinancialFact` with **only** `company_id` as predicate (`service.py:194–209`) — no date bound anywhere. Meanwhile:

- bars are bounded: `DailyPrice.date <= as_of` (`service.py:91`);
- the freshness document is bounded: `publication_date.is_not(None)` + `publication_date <= as_of` (`service.py:250–251`).

So for a past `as_of`:

- `present` (line 235–240, critical-label completeness) counts facts from filings published **after** `as_of`;
- `observed` (line 274, `len(periods)` vs expected depth 8) counts periods not yet filed at `as_of`;
- `validator.validate_facts(facts)` (line 265) accrues errors/warnings from future filings;
- `no_rows` (line 211) is decided on unfiltered sets.

Exposure is reachable today from the public API: `POST /api/data-quality/companies/{id}/assess?scope=…&as_of=…` passes any date straight through (`api/data_quality.py:55,60`). Default flow (`as_of` omitted → today) is unaffected.

**Spec-gap, not implementer error:** task-5-brief.md line 36 pinned exactly this row-loading ("`FinancialPeriod`, `FinancialFact`, `FinancialDocument` (documents with `publication_date <= as_of` for freshness)" — the parenthetical scoped the cutoff to freshness only). The implementer followed the brief.

## Ruling: **(a)** — `as_of` must bound fact and period loading

Option (b) ("accept that `as_of` only bounds freshness/depth arithmetic") is **rejected**. Reasons:

1. **Plan Global Constraints, line 21:** "Backtesting and any `as_of`-parameterised analysis may only use rows whose `publication_date <= as_of` (AGENTS.md rule 4)." A `POST …&as_of=2024-07-01` assessment is an `as_of`-parameterised analysis. Shipping (b) leaves a documented, user-reachable violation of a hard project rule.
2. **Task 2 already established the codebase-wide predicate.** Plan lines 167–171 ruled a period "usable only if at least one of its documents has `publication_date <= as_of_date`", implemented at `period_selector.py:108–124`. Two scopes of the same product must not disagree about what a date means.
3. A DQ score that overstates data availability at a past date is wrong in the direction that matters: it would later back a backtest/signal on information nobody had.

## Pinned semantics for the fix

1. **Facts** = company facts whose **own document** (`FinancialFact.document_id → FinancialDocument`) has non-null `publication_date <= as_of`. SQL `publication_date <= as_of` already excludes NULLs; keep the explicit `is_not(None)` for parity with lines 250–251 if the implementer prefers. This filtered set feeds `present_set`, `validator.validate_facts`, and the `if not facts` issue check (line 284).
2. **Periods (`observed`)** = company periods having **≥ 1 document** with non-null `publication_date <= as_of` (EXISTS subquery on `financial_documents.period_id`). Mirrors `period_selector.filter_by_publication_date` exactly.
3. **`no_rows`** (line 211) is decided on the **filtered** sets: no qualifying periods AND no qualifying facts.
4. **NULL `publication_date` does not satisfy the cutoff at any `as_of`** (consistency with `period_selector.py:124`: `if doc.publication_date and doc.publication_date <= as_of_date`). Consequence, accepted: a company whose documents are all undated lands in the existing `no_rows` branch and gets the already-pinned strings ("validation: no facts to validate — check not run", "freshness: no publication dates available — check not run" — brief line 49). No new branch, no new strings. In the rare all-filings-after-`as_of` case that same freshness string reads "no publication dates available", pinned as an accepted approximation meaning "none available by `as_of`".
5. **Untouched:** the `latest_doc` freshness query (already bounded); `price_history` (already bounded); `company_profile` — it has no publication date at all, so a past `as_of` assesses the current row state; that is a structural limitation (would need row history, out of scope). Its staleness is already fail-safe: `updated_at > as_of` → negative `days_stale` → `freshness_score` floors to 0.0 (`scores.py:107`), so future state can never inflate the score. Documented here; no code change.

## Timing: dedicated Task 5 follow-up commit, **before** Task 6 implementation

- **Not folded into Task 6.** task-6-brief.md line 50 explicitly puts `app/dataquality/**` out of Task 6's scope; folding would force a brief amendment and mix ingestion with scoring in one commit.
- **Not deferred to a later task.** No roadmap task after Task 6 owns `dataquality/service.py` — deferral has no owner (same test as R11).
- **Safe to insert now:** `git status` shows no modified files outside `.workflow/` — Task 6's code has not been started, only authorized. The fix is two queries + one test + a brief amendment.
- **Work:** staff-backend, TDD (AGENTS rule 7) — failing test first in `backend/tests/test_data_quality_api.py`, then the two query changes in `backend/app/dataquality/service.py`, then amend task-5-brief.md line 36 row-loading cell in place (precedent: R10 amended a brief in place). One commit: `fix(dataquality): bound fact/period loading by as_of publication_date`.
- **Required test coverage:** for `financial_statements`, a period/filing published before a past `as_of` counts (`present`/`observed` include it); a filing published after that `as_of` is excluded from `present`, `observed`, and validation totals but included when the same company is assessed at a later `as_of`; a document with NULL `publication_date` is excluded at any `as_of` (pins pin 4).
- **Gates:** `pytest -q` green, `ruff check app tests` clean, `mypy app` no new errors vs `mypy-baseline.txt` (R6).
- **Review:** analyst re-verifies the original finding is closed (it raised it); tech-lead final verdict. Then staff-backend proceeds to Task 6 with its brief unchanged.

## Cost if wrong

If (a) were wrong (i.e. `as_of` were meant as a cosmetic label), the cost is two join predicates and one test on an opt-in parameter nobody calls with a past date yet. If (b) were shipped and later relied on by Phase 9 backtesting (plan line 83), every historical DQ score would quietly encode future filings — an AGENTS rule-4 defect baked into persisted rows (`data_quality_assessments` upserts per `(company_id, scope, as_of, methodology_version)`, so wrong rows would need re-assessing). Asymmetric: fix now.
