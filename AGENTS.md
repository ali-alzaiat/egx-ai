# AGENTS.md — EGX AI Project Instructions

## Core Principles

1. **Deterministic calculations only.** Financial formulas (P/E, DCF, CAGR, ROE, Shariah screening) must be implemented in code — never delegated to an LLM.
2. **No fabricated data.** Never invent market data, financial values, company information, or sources.
3. **Source everything.** Every financial number must have a traceable source (document, page, date).
4. **No look-ahead bias.** Backtesting must only use information whose `publication_date <= simulation_date`.
5. **Shariah methodology must be versioned.** Do not hard-code thresholds. Store methodology version and source.
6. **AI interprets, not invents.** LLMs analyze supplied data and explain findings — they do not generate financial facts.
7. **Tests required.** Every financial formula must have unit tests covering edge cases (zero, negative, missing).
8. **Don't expose secrets.** API keys, database credentials — environment variables only, never in source.
9. **No trading execution.** This is a research tool. Never implement buy/sell order execution.
10. **Don't present AI output as certainty.** Use phrases like "potentially undervalued under these assumptions" not "BUY".

## Working Style

Before writing code:
1. Inspect the repository and existing code.
2. Identify which phase the project is in.
3. Implement the smallest coherent increment.
4. Run tests and lint.
5. Fix errors before moving on.

## File Conventions

- Backend: Python 3.12+, FastAPI, SQLAlchemy 2.x, Pydantic
- Frontend: React 19, TypeScript, Vite, TanStack Query
- Tests: pytest (backend), vitest (frontend)
- Linting: Ruff (backend), ESLint (frontend)

## Data Sources

Design ingestion around official/primary sources:
- Egyptian Exchange (EGX)
- Financial Regulatory Authority (FRA)
- Company investor-relations pages
- Official annual/quarterly reports

Never bypass CAPTCHAs, authentication, or robots restrictions.

## Error Handling

For missing financial data:
```json
{"value": null, "status": "INSUFFICIENT_DATA", "reason": "..."}
```
Never substitute zero for missing information.
