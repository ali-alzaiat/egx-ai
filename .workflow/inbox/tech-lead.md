# Inbox: tech-lead

From: router (user directive) · 2026-10-09
User's words: "fix the gaps and while the other agents are fixing the gaps make the UX
expert test the current UX of the whole app and enhance it based on the other apps because
I don't like the current UX."

Two streams are ready for your ruling and task briefs.

## Stream A — fix the gaps (stale data + empty data-quality scores)
- Architect contract: `.workflow/design/refresh-and-assess-contract.md` (Tarek). It pins a
  `POST /api/ingestion/sync` → 202 + detached in-process job, polled by
  `GET /api/ingestion/sync/status`; the job runs universe → prices → assessment, so one
  refresh populates `data_quality_assessments` for all companies; `GET /api/data-quality/…`
  stays read-only; `~15` safety bounds; full JSON shapes, TS types, five mock payloads and
  cost-if-wrong tables. Architect ended `NEXT: tech-lead`.
- Your job: rule on it (accept as written, or amend — record the ruling in
  `.workflow/decisions/` as the next R-number) and author the staff-backend brief at
  `.superpowers/sdd/2026-10-08-competitive-enhancement-roadmap/task-refresh-assess-brief.md`.

## Stream B — app-wide UX overhaul
- Live audit: `.workflow/design/app-ux-audit.md` (Salma; 17 findings F1–F17 from a live
  Playwright walkthrough — the four headline features are unreachable/misleading, the
  dashboard lies, etc.).
- Competitor research: `.workflow/research/app-wide-ux-patterns.md` (Nadia; every claim
  cited).
- Your job: rule on the v1 scope/cut line — what a first overhaul fixes vs defers, grounded
  in the audit and the research shortlist — and author the ux-expert brief at
  `.superpowers/sdd/2026-10-08-competitive-enhancement-roadmap/task-ux-redesign-brief.md`.
  Salma then produces the enhancement spec (design only; staff-frontend implements after).

## Sequencing you must pin
- Stream A backend (`backend/app/**`, tests) and Stream B design (`.workflow/design/`) are
  disjoint → run in parallel now.
- Both frontend outputs (the refresh button + the UX overhaul) must be implemented by ONE
  staff-frontend task at the end, to avoid file conflicts. Pin that in the briefs.

## Also dispose of
- Pending **Task 7 review** (impl `6486ae7`, review never dispatched) and the **Task 8
  review findings** (vitest env jsdom→node flagged Important; minor items). Either fold
  their disposition into these rulings/briefs or defer them with an explicit ledger note.
  Do not leave them silently open.

Return the rulings inline (the router files what you don't). End with exactly one contract
string: NEXT: staff-backend, BLOCKED: <question>, ASK USER: <question>, or DONE.
