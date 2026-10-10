# R24 — Phase 2 backend verdict (fix-list, then ship)

**From:** Mostafa (tech-lead) · 2026-10-10
**Trigger:** qa-api Phase 2 conformance review — conformant to R22/R23, NO hard
blockers, gates green, 6 ruling requests.
**Evidence re-verified by tech-lead (not taken on memory):**
`backend/app/api/industry.py`, `backend/app/industry/service.py:51-64,86-118,159-185`,
`percentiles.py`, `constants.py:26-126`, `seed.py`, `backfill.py:90-141`,
`models/industry.py:22-192`, `repositories/industry.py:34-166`,
`tests/test_industry_api.py:193-240`, `app/metrics/definitions.py:273-300`;
`reason`-key convention via repo-wide grep (metrics/valuation/screening/signals/
technical APIs all emit `"reason"`); AGENTS.md Error Handling pins
`{"value": null, "status": "INSUFFICIENT_DATA", "reason": "..."}`.
Gates run by tech-lead: industry suites 29 passed; `ruff check app tests` clean;
`mypy app` 0 errors/115 files; migration `012_industry.py`
(`revision="012"`, `down_revision="011"`) chains on `011_data_quality.py`. The
R21-known `test_full_refresh_happy_path` census issue is untouched by this diff.

## Rulings

**Q1 — `explanation` key vs `reason` convention: ADD ALIAS (fix F1).**
R22 R5 orders a "human-readable explanation string", so `explanation` stays; but
every other domain API speaks `reason` (AGENTS.md error pattern). Both are right —
emit both keys with the identical string. Zero breakage: no frontend consumes this
router yet, existing tests asserting `explanation` keep passing.

**Q2 — 3-branch seed vs full 74-industry GICS tree: SUFFICIENT, no change.**
Schema is the full 4-level tree (`models/industry.py`); all 11 GICS sectors and
all 18 EGX sectors seed; chains materialize exactly the 3 profiled branches and
only the 4 verified EGX→GICS mappings exist (`constants.py:94-99`) — unverified
mappings are correctly absent per rule 2 (no fabrication). R22 R1 accept
("≥1 GICS node with source+date") is met; unmapped sectors degrade safely
(`gics_chain…` → None → `gics: None`, default profile). Later phases extend via
the same idempotent seed path.

**Q3 — override version-stamped, no history: CONFIRMED, no history table.**
R22 R3 accept requires only persist + GET-uses-it. `CompanyPeerOverride` stamps
`methodology_version` + `updated_at` on idempotent upsert. Version *history*/audit
is a Phase 10+ concern, not Phase 2 exit criteria — do not build it now.

**Q4 — PUT `[]` semantics: KEEP "explicit empty override", ADD TEST (fix F3).**
Current behavior is the coherent one: PUT `[]` persists an empty override →
`resolve_peers` returns `([], "override")` → zero peers → INSUFFICIENT_DATA floor
(never a 1-of-1 rank, consistent with R5). "Clear" would conflate explicit-empty
with absent and needs DELETE semantics nobody specced. Pin it with a regression
test; no service change.

**Q5 — `display_name` echoes `metric_key`: WIRE REAL LABELS (fix F2).**
Stronger than the "note for Phase 3" qa-api suggested, because the source already
exists in-repo: `app.metrics.definitions.get_metric(code).display_name`
(e.g. `roe` → "Return on Equity"), and Phase 2 profiles use only real codes
(`constants.py:104`), so lookup cannot miss today. Use definition label with
`metric_key` fallback.

**Q6 — stress paths unprobed: ACCEPT ASGI defaults, fold into Phase 3 QA.**
Unlike Stream A, these endpoints are stateless GET/PUT with idempotent upsert —
no detached job, no single-flight surface. No Phase 2 work; Phase 3 QA probes
concurrency/load alongside the valuation UI.

## Verdict: FIX-LIST (then ship — no rework)

- **F1.** `service.py::peer_snapshot` — add `"reason"` key (same string as
  `"explanation"`) on each percentile entry + one test assertion.
- **F2.** `service.py:165` — `display_name` from `get_metric(row.metric_key)`,
  fallback `metric_key` + test (`roe` → "Return on Equity").
- **F3.** `tests/test_industry_api.py` — PUT-`[]` regression test: 200, GET basis
  `"override"`, `items == []`, percentiles `INSUFFICIENT_DATA`.
- After: staff-backend runs industry suites + ruff + mypy, qa-api re-verifies F1–F3
  + full gates, Phase 2 ships.

## Phase 2 frontend surface: NOT wanted

R22 is backend-shaped (one domain router, no UX design, no frontend brief). Per
pipeline, frontend builds from a UX design + frozen contract — neither exists for
peers/percentiles. Surface lands with the Phase 3 valuation UI per standing
req 3; no staff-frontend task now.

Skipped: full-suite pytest re-run (industry suites + qa-api's green gates suffice;
R21 census issue out of scope). Risk: `reason`/`explanation` dual keys must collapse
to one when the Phase 3 contract freezes — flagged for the architect then.
