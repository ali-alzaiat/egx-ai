# Inbox: researcher

From: router · 2026-10-08
Task: Roadmap Phase 1, Task 5 — assessment service + API (data-quality scoring for EGX stocks).
Context: backend/app/dataquality/service.py + backend/app/api/data_quality.py to be created. Score components: price_history (bar count vs expected trading days, source reliability), company_profile (field completeness, freshness), financial_statements (period count vs 8, document freshness, CRITICAL_FACT_LABELS completeness, validator errors).
Research ask: How do competitors (Bloomberg, Refinitiv, Morningstar, local EGX data vendors, open-source data-quality frameworks) score/communicate financial data quality to users? What granularity, what UI patterns, what disclaimers?
Deliverable: file findings to .workflow/research/task-5-data-quality-scoring.md (router will file).
End with: NEXT: pm, BLOCKED: <question>, or DONE.
