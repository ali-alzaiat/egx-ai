# Agent rules (read this, not the full CONTRACT/AGENTS, unless your task needs them)

## Product invariants (AGENTS.md, condensed)
1. Financial formulas are deterministic code with unit tests (zero / negative / missing cases). Never delegated to an LLM.
2. Never fabricate data. Missing values: `{"value": null, "status": "INSUFFICIENT_DATA", "reason": ...}`; never 0, never blank.
3. Every number traces to a source (document, page or vendor + fetch date). Filings outrank vendor data.
4. No look-ahead bias (`publication_date <= simulation_date`). Methodologies are versioned and sourced, never hard-coded thresholds.
5. No certainty wording ("BUY", "guaranteed", "will rise"). No trade execution. Secrets only in env vars.
6. Python: full type hints, `mypy app` clean, ruff clean. Frontend: React 19 + TS + TanStack Query; every string through `t()`; Arabic RTL; Western digits (`ar-EG-u-nu-latn`).

## Runtime (Windows, Claude Code)
- Python: `backend/.venv/Scripts/python -m …`; run pytest/ruff/mypy from `backend/`. Tests use the isolated `egx_ai_test` DB.
- API needs `Authorization: Bearer $API_TOKEN` (repo-root `.env`); `/api/health` is public. Backend dev server: port 8000.
- UI checks: built-in browser. Open your own tab; close only tabs you opened; reset viewport to desktop when done.
- Never write to the dev database unless the brief says so. Never commit, merge or switch branches (router only).

## Token discipline (mandatory)
- Your brief is the top (only) entry in `.workflow/inbox/<you>.md`. Read files only as your task needs them: Grep first, then read targeted line ranges. Don't re-read files you already read.
- Prefer text over images: `get_page_text`, `read_page`, `javascript_tool` over screenshots. Screenshot only when layout is the finding, at `scale` ≤ 0.5.
- Web research: targeted searches, fetch only pages you will cite.
- Gates: paste only the last 3 lines of each command's output.

## Owner decisions (mandatory)
- Never decide architecture (schema, migrations, data model, patterns, new dependencies/services, auth) or UX (layout, navigation, flows, what a screen shows, copy tone, visual direction) yourself. Write 2–4 options with trade-offs and one recommendation, then end with `ASK USER: <question>` (architect, ux-expert, pm, tech-lead) or `BLOCKED: <choice>` (everyone else). Details inside an approved decision or spec need no asking.

## Deliverables and handback
- Write your deliverable yourself to the path in your brief (reviewers may write only under `.workflow/`; implementers only in their code scope).
- Your final message is a handback of at most 150 words: deliverable path(s), the key decisions or findings, open risks, and exactly one contract string: `NEXT: <agent>` | `BLOCKED: <question>` | `ASK USER: <question>` (tech-lead, architect, ux-expert, pm) | `DONE`.
