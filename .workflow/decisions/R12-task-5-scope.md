# R12 — Task 5 scope: assessment service + API

**From:** pm · 2026-10-08
**Inputs:** .workflow/research/task-5-data-quality-scoring.md, roadmap plan lines 211–231

## Rulings on the plan's proposed interfaces

| Interface | Ruling | Rationale |
|---|---|---|
| DataQualityService.assess(company_id, scope, as_of=None) | **Accept** | Per-scope inputs as planned. No competitor finding contradicts it. |
| DataQualityService.latest(company_id, scope, methodology_version=None) | **Accept** | DataQualityScore already carries components + issues (Task 1, persisted JSONB Task 4) — satisfies "composite + breakdown". |
| Routes: GET …?scope= → {items, methodology_version}, POST …/assess, 404 unknown company | **Accept + amend** | Amend below (R12.1: scale in payload). |
| Disclaimer: "Data quality describes the available inputs. It is not an assessment of the company." | **Accept** | Matches Mubasher's local precedent; keeps AGENTS.md rule 10. Ship on both GET and POST. |
| Screening GET gains "data_quality": {…} | null (scope financial_statements) | **Accept** | null = not yet assessed (withheld). Embedded object includes status, so a POOR score stays visible — INSUFFICIENT_DATA/withheld distinct from a low score. |

## Amendments and additions

**R12.1 — Add `scale` to API responses (both routes).** ISO 8000-8(a): state the scale used. Module-level constant: "scale": "0-100; higher is better; status MISSING|DEGRADED|POOR|OK". One key, no new types.

**R12.2 — Encode "check not run" in existing `issues`, not a new `checks_not_run` field.** When a component's underlying data is absent (no facts to validate → validation unknown; no document dates → freshness unknown), service appends an `issues` string naming the check, e.g. "validation: no facts to validate — check not run". Zero schema change; caveat reaches the user.

**R12.3 — Component `reason` strings must carry the concrete number/date.** e.g. "latest bar 2026-09-30; 412/430 expected trading days", "latest filing published 2026-04-12". Sits inside already-persisted components JSONB.

## Rejected (with cost if wrong)

**R12.4 — Reject: withhold the score below a gate (Morningstar 67% pattern).** Withholding hides exactly the signal users need. DQ score describes data availability — a POOR/MISSING status with score 0 is the honest answer. Gate pattern applies to investment ratings, which we don't ship.

**R12.5 — Reject: per-check pass/warn/fail enums (Soda / Great Expectations shape).** Component score + reason already conveys severity; enum states would grow Task 1's frozen QualityComponent. No EGX-local vendor publishes a DQ score at all (open lane). Cost if wrong: minor UI polish later, cheap to add in a frontend phase.

## Scope guard

Task 5 scope = plan's file list and steps unchanged, plus: one `scale` key, issues-string convention (R12.2), reason-format convention (R12.3). Fold the three into existing planned tests (one assertion each in round-trip and screening-null tests) — no new test files, no new models, no Task 1 interface changes.
