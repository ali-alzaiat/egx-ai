# Inbox: staff-frontend-a4 (Lane A4 — Industry peers strip)

From: router (frontend parallel lanes) · 2026-10-16
Task: Own Lane A4 end-to-end: CREATE `frontend/src/components/PeersTab.tsx` + `frontend/src/components/PeersTab.css` ONLY (both new — neither file exists yet).

Context (already landed by router, do NOT touch): hook `useIndustrySnapshot` + `putPeerOverride` in `client.ts`, types `IndustrySnapshot` et al in `types/index.ts`. Backend: verify shapes yourself in `backend/app/api/industry.py` + `IndustryService.peer_snapshot` — `GET /api/industry/companies/{company_id}` (sector/egx_sector/gics, peers {basis, items}, profile {profile_id, methodology_version}, percentiles[] with value/status/explanation, n_peers, methodology_version, as_of); `PUT …/peers` `{peer_company_ids[]}` override (persists). Render: sector/industry + peer chips + per-metric percentile bars with the written explanation + editable peer list with save (mutation invalidates `["industry", id]`). Router wires the route + tab after you return — do NOT touch `App.tsx`/`CompanyTabs.tsx` yourself; include exact wiring instructions (route path `/companies/:ticker/peers`, tab label `Peers`).

Contract: `.workflow/design/frontend-catchup-contract.md` (Batch A.4 + cross-cutting rules). Conventions: React 19 + TS + TanStack Query; INSUFFICIENT_DATA badges; methodology/profile-version footnote; rule-10 copy (no BUY); vercel-react-best-practices skill, client/rerender/bundle/rendering/js rules only.

FORBIDDEN: every other existing file, backend/**, .workflow/**. No commits. No `npm run build`, no `npm test` (shared tree — router runs gates after merge). You may run `npx tsc --noEmit` and `npx eslint <your two files>` only. The component takes `companyId: string` (and optionally `ticker`) as props — do NOT call `useParams` inside (router mounts it under the company route).

Deliverable: the two new files, complete and polished. Return: files created, exported props, wiring instructions, tsc/eslint pasted output. End with exactly one: NEXT: router | BLOCKED: <question> | DONE.
