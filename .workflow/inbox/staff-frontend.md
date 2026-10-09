# Inbox: staff-frontend

From: router (via architect + ux-expert) · 2026-10-09
Task: Roadmap Phase 1, Task 8 — data-quality card + navigation fixes.
Design: .workflow/design/data-quality-card-ux.md (implement EXACTLY this)
Contract: .workflow/design/data-quality-contract.md (exact API shapes, TS types, mock payloads)
Plan: docs/superpowers/plans/2026-10-08-competitive-enhancement-roadmap.md lines 267-279
Deliverable: frontend/src/lib/quality.ts + quality.test.ts, frontend/src/components/DataQualityCard.tsx, wire useDataQuality hook, mount in CompanyDetail; fix client.ts:154 escaped `${ticker}`; remove dead nav links (/watchlist, /research, /alerts) in Layout.tsx; add .dq-* CSS.
Gates: npm test (vitest), npm run lint, npm run build all clean.
Commit: ONE commit `feat(frontend): data-quality card, fix signal hook path, drop unroutable nav links`.
Report to: .superpowers/sdd/2026-10-08-competitive-enhancement-roadmap/task-8-report.md
