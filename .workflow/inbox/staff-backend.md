# Inbox: staff-backend

From: router (user directive) · 2026-10-09
Task: Backend typing cleanup — make `mypy app` CLEAN.
Current: 51 errors in 25 files. All must be fixed (AGENTS.md: mypy app clean, no baseline deferrals).
Main classes: ~40 `Missing type arguments for generic type "dict"` (bare `dict` -> `dict[str, Any]`), `no-untyped-def` in repositories/metrics.py:19, ingestion/financial_service.py:229,248, signals.py var-annotated/arg-type.
Files: backend/app/** only. No behavior change — annotations only.
Gates: mypy app clean (0 errors), pytest -q green (336 expected), ruff clean.
Report to: .superpowers/sdd/2026-10-08-competitive-enhancement-roadmap/task-typing-report.md
