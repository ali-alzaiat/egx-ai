# Inbox: tech-lead

From: router (qa-ui findings, Batches B–D) · 2026-10-16
Task: Rule on three qa-ui findings + final verdict on the Batch B–D frontend merge. Full evidence in qa-ui result `ses_ebadb62d0ffeBDCMm30h4j1vqR` (handoffs.log); router already fixed F1 (duplicate key), F2 ([object Object]), F5 (thesis score object crash), F6 (raw JSON), F8 ( Thesis/Disclosures tabs added) — gates re-verified green (tsc/eslint/build 0 warnings, vitest 10/10).

Rulings needed (next R-number):
- F4: `GET /api/screening/companies/{id}/purification` (and the screening GET itself when unassessed) 404s in console on page load; page degrades gracefully to empty state. Is an expected-empty-state 404 acceptable console noise, or must the frontend pre-check (extra round-trip) to keep the console at zero errors?
- F3: after "Run screening", the EGX33 side panel still shows "Not screened yet" until reload — stale read (query invalidation misses the membership query). Fix-list item or accept-and-carry with a filed follow-up?
- F7: score page renders "Buy zone (display only)" + "Buy Zone not computed" labels; page also carries "not a recommendation to buy or sell". Does the "Buy zone" label violate AGENTS.md rule 10, or is it compliant hedged display-only copy?

Then: final verdict SHIP / FIX-LIST / REWORK on the Batch B–D merge. End with exactly one: NEXT: <agent> | BLOCKED: <question> | ASK USER: <question> | DONE.
