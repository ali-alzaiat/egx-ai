# Data-Quality Card — UX Design

**For:** staff-frontend (Task 8) · **From:** ux-expert · 2026-10-09
**Inputs:** `.workflow/research/data-quality-ux-patterns.md`, `.workflow/design/data-quality-contract.md`
**Rule:** implement exactly this. Every field shown here exists in the contract; nothing outside it is rendered.

## 1. Placement

On `CompanyDetail.tsx` (`/companies/:ticker`), full-width card **between the `.page-header` and the first `.card-grid`** — above Ticker/ISIN/Sector cards, Latest Close and Historical Prices. It is a trust qualifier for every figure below it.

Data source: `GET /api/data-quality/companies/{company_id}` (all scopes). The screening embed is not used on this page.

**Multiple scopes:** the endpoint returns up to three assessments (`price_history`, `company_profile`, `financial_statements`); scopes never assessed are omitted. Render **one section per returned item, in canonical order** (`price_history` → `company_profile` → `financial_statements`), each with its own score + badge + components + issues. No cross-scope aggregate exists in the contract — do not compute one.

## 2. Layout (element order)

```
.card .dq-card
  h2 "Data quality"  (.section-title)
  p  "How much usable data we have for this company, on a 0–100 scale. Higher is better."  (.dq-definition)

  per scope section (.dq-scope):
    scope head (.dq-scope-head): "Financial statements"  |  right: "As of 2026-10-09"
    score row (.dq-score-row): "85.5 / 100" (left)   [ ✓ Good ] (.status-badge, right)
    per component (.dq-component):
      head line: "Completeness" | "weight 30%" | "100 / 100"
      bar (.dq-bar > .dq-bar-fill)  role="progressbar"
      reason line (.dq-component-reason): "5 of 5 required items present"
    issues (.dq-issues) — only when issues.length > 0 and status !== MISSING
      ul of issue strings, each prefixed "!" glyph

  p disclaimer (API `disclaimer`, verbatim)
  p footer: "Bands: 70+ Good · 40–69 Partial · below 40 Poor · Methodology v1.0"
```

No gauge, ring, or radar — number + word + breakdown.

## 3. Per-element spec

### Score
- `score` with 1 decimal, e.g. `85.5 / 100`.
- `status === "MISSING"`: render `—` (never `0 / 100`); add `sr-only` "not scored". Neutral grey.
- Never a bare number — badge always adjacent.

### Status badge (reuse `.status-badge` + modifiers; icon `aria-hidden`, label carries meaning)

| status | Label (exact) | Icon | Class |
|---|---|---|---|
| OK | `Good` | ✓ | `.status-badge.healthy` |
| DEGRADED | `Partial` | ! | `.status-badge.warning` |
| POOR | `Poor` | ✕ | `.status-badge.error` |
| MISSING | `Insufficient data` | – | `.status-badge.unknown` |

Badge `title="Good: 70–100 · Partial: 40–69 · Poor: below 40 · Insufficient data: no data to assess"`.

### Scope header
- Label: `Price history` / `Company profile` / `Financial statements`.
- Right: `As of {as_of}`.

### Component rows (one per `components[]`, contract order)
1. Head line: `label` (left) · `weight {Math.round(weight*100)}%` (center, muted) · `{Math.round(score)} / 100` (right).
2. Bar: fill width = `score`%, color by band; `role="progressbar"`, `aria-valuenow={score}`, `aria-valuemin=0`, `aria-valuemax=100`, `aria-label="{label}: {score} of 100, weight {pct}%"`.
3. Reason line: `reason` verbatim, muted small text.

**MISSING exception:** head line `label` · `weight 30%` · **no score, no bar**; show `reason` only.

### Issues list
- Render only when `issues.length > 0` **and `status !== "MISSING"`** (issue strings hard-code `(0/100)`; in MISSING the headline + reasons already say it). Add a code comment.
- Header `Issues`; items are the API strings verbatim, each prefixed `!` (aria-hidden); muted color (badge carries severity; strings are advisory facts, never red).
- No drill-down links (no route exists).

### Disclaimer + footer
- Line 1: API `disclaimer` **verbatim** (never hard-code).
- Line 2, muted: `Bands: 70+ Good · 40–69 Partial · below 40 Poor · Methodology v{methodology_version}`.

## 4. Color semantics + cut-offs

| status | cut-off | color | icon | meaning |
|---|---|---|---|---|
| OK | score >= 70.0 | `--green` | ✓ | data sufficient |
| DEGRADED | 40.0 <= score < 70.0 | `--yellow` | ! | partial coverage |
| POOR | score < 40.0 | `--red` | ✕ | weak coverage |
| MISSING | no rows (forced 0.0) | `--text-secondary` on `--border-subtle` (`.status-badge.unknown`) | – | neutral: nothing to assess — not bad data, not a judgment on the company |

- Component bars use the same three bands on the component's own score; MISSING scope bars are omitted.
- **color + icon + text**, never color alone. MISSING is grey, never red, never zero.

## 5. Exact copy strings

| Where | String |
|---|---|
| Card title | `Data quality` |
| Definition line | `How much usable data we have for this company, on a 0–100 scale. Higher is better.` |
| Score unit | `{score} / 100` (MISSING: `—`) |
| Badge labels | `Good` / `Partial` / `Poor` / `Insufficient data` |
| MISSING helper (under score, only when MISSING) | `Not enough data to score. This is not a judgment on the company.` |
| Scope labels | `Price history` / `Company profile` / `Financial statements` |
| As-of | `As of {as_of}` |
| Weight | `weight {pct}%` |
| Issues header | `Issues` |
| Footer bands | `Bands: 70+ Good · 40–69 Partial · below 40 Poor · Methodology v{methodology_version}` |
| Disclaimer | API `disclaimer` field, verbatim |
| Empty state | `No data-quality assessment has been run for this company yet.` |
| Loading | `Loading data quality...` |
| Error | `Couldn't load data quality.` |

## 6. Empty / loading / error states

- **Loading:** card frame with `<div className="loading">Loading data quality...</div>`; no layout jump.
- **Empty (`items: []`):** title + definition + neutral block `.status-badge.unknown` styling: grey `–` + `No data-quality assessment has been run for this company yet.` + disclaimer footer. Distinct from MISSING.
- **Error:** `<div className="alert alert-error">Couldn't load data quality.</div>`. No retry button. Never silently hide the card.
- **Company not found:** page short-circuits before the card.

## 7. Implementation notes (staff-frontend)

- **New classes** (append to `index.css`, no new tokens/deps, icons are unicode): `.dq-card`, `.dq-definition`, `.dq-scope`, `.dq-scope-head`, `.dq-score-row`, `.dq-score`, `.dq-score.missing`, `.dq-score-note`, `.dq-component`, `.dq-component-head`, `.dq-component-reason`, `.dq-bar`, `.dq-bar-fill`, `.dq-issues`, `.dq-issue`, `.dq-footer`, `.dq-disclaimer`, `.dq-empty`.
- **Reuse as-is:** `.card`, `.section-title`, `.status-badge.healthy/.warning/.error/.unknown`, `--green/--yellow/--red` + `-bg` tokens, `--text-secondary`/`--border-subtle`, `.loading`, `.alert .alert-error`, `--radius`/`--radius-lg`/`--transition`.
- **Bar:** track `background: var(--border-subtle)`, height ~6px, `border-radius: 9999px`; fill `width: {score}%`, `background: var(--green|yellow|red)`, transition on width.
- **Types:** paste contract TS interfaces verbatim into frontend types; mock with the two contract payloads.
- **Formatting:** score → `toFixed(1)`; component score → `Math.round()`; weight → `Math.round(weight * 100)`; scope order → fixed array sort.
- **A11y:** badge text is the accessible name; icons `aria-hidden`; bars `role="progressbar"` with `aria-label`; `—` gets `sr-only` "not scored"; issues a real `<ul>`; disclaimer a `<footer>`.
- **Scope filtering:** render whatever `items` contains; omitted scope = not assessed = absent, not MISSING.
