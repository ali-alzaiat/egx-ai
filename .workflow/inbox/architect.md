# Inbox: architect

From: router (user directive) · 2026-10-09
Task: Define the frontend/backend API contract for the data-quality feature so backend and frontend can build in parallel (frontend against mocks).
Source of truth: backend already ships Task 5 — read backend/app/api/data_quality.py + screening.py GET response. Do not invent fields.
Deliverable: .workflow/design/data-quality-contract.md — endpoints, request/response JSON shapes with exact fields, status enum, scale/disclaimer keys, the screening embed shape, and the TypeScript types the frontend should declare. Explicit enough that frontend can mock it.
Report to: returned inline or the design file.
