# R50 AI analysis: contract (source of truth for backend and frontend)

Rulings: `.workflow/decisions/R50-ai-analysis.md` (B1–B11). Extends the R49 contract
(`R49-ai-assistant-contract.md`); everything there still holds unless changed here. AGENTS.md rules
1, 6, 10 bind. Bump `AI_PROMPT_VERSION` to `assistant-1.1` (`assistant-1.2` after the live check: percentages and units for display).

## 1. EGX30 benchmark (B10)

- Migration 028 adds `index_prices(index_code VARCHAR(20), trade_date DATE, close NUMERIC(20,4), source VARCHAR(40), fetched_at TIMESTAMPTZ, PK(index_code, trade_date))`.
- `ingestion/egx/provider.py` (Yahoo) fetches `^CASE30` as `index_code = "EGX30"` in the price phase of `ingestion/jobs.py`; a failure is logged and does not fail the job. No synthetic fallback.
- Repository `repositories/index_prices.py`: `series(index_code, start, end)`.

## 2. Performance (B9) — pure module `performance/engine.py` + `performance/constants.py`

- `PERFORMANCE_METHODOLOGY_VERSION = "performance-1.0"`; windows `1M=21, 3M=63, 6M=126, 1Y=252` trading days, plus `YTD` (last close of the previous calendar year).
- `price_returns(closes, as_of)`: per window `{return, start_date, end_date}` as a fraction (Decimal, 4dp), or `{"status": "INSUFFICIENT_DATA", "reason"}` when the series does not reach back. Uses the latest close on or before each start date; no look-ahead.
- Same function over the EGX30 series; `relative = stock − index` only when both exist.
- `fundamentals_growth`: revenue and net income TTM + YoY and the TTM net margin, reusing `ingestion/disclosures/comparison.py` (TTM needs four reported quarters, else INSUFFICIENT_DATA), from `latest_approved` statement lines.
- Tool `company_performance(ticker)` in `ai/tools/analysis.py`, standard envelope, source "EGX AI performance engine over stored prices, EGX30 and approved statement lines".

## 3. Data cross-checks (B11) — `dataquality/crosscheck.py` (pure) + `dataquality/crosscheck_service.py`

`CROSSCHECK_METHODOLOGY_VERSION = "crosscheck-1.0"`. Each check returns `{code, status: "pass"|"warn"|"fail"|"insufficient_data", detail, evidence}`:

| code | What it checks | warn / fail |
|---|---|---|
| `provenance` | Share of the latest approved statement lines backed by a filing (document + page) vs vendor-only | warn < 80% filing-backed; fail when no line is filing-backed |
| `cross_source` | Same company/period/ontology code with a filing-backed line and a `vendor_aggregator` line: relative difference | warn 1–5%; fail > 5%. **Evidence shows only the band and our value, never the vendor value.** |
| `accounting_identity` | Total assets = total liabilities + total equity (and other identities whose ontology codes all exist) per period | warn 0.5–2%; fail > 2% |
| `price_sanity` | Non-positive closes, one-day moves beyond the EGX daily limit without a split, gaps > 5 trading days in the last year | warn on gaps; fail on non-positive or unexplained limit breaches |
| `freshness` | Last close age and the latest reported period vs today | warn price > 3 trading days or period > 2 quarters behind; fail > 10 days / > 4 quarters |

Thresholds live in `dataquality/constants.py` with the version. Migration 028 also adds `data_crosschecks(id, company_id, check_code, status, detail, evidence JSONB, methodology_version, computed_at)`; each run appends rows; "latest" = the newest run per company. Runs: after the assessment phase of `ingestion/jobs.py` for the synced tickers, and from `continuous/trigger_service.py` when facts land for a company.

API (router `api/data_quality.py`, prefix `/api/data-quality`):
- `GET /companies/{company_id}/crosschecks` → `{company_id, computed_at, methodology_version, overall, checks: [...]}`; `overall` = the worst status; 404 unknown company; `{checks: [], computed_at: null}` when never run.
- `POST /companies/{company_id}/crosschecks/run` → runs now, returns the same shape.

Tool `data_check(ticker)`: the latest stored run in the envelope (runs it first when none exists).

## 4. Web search (B3–B6)

- `catalog.py`: `CatalogModel.web_search: bool` (Sonnet 5.5, Opus 5.5, both Gemini models true; Haiku 4.5 and OpenAI false). A test asserts each true entry has `web_search_options` in LiteLLM's supported params.
- `gateway/base.py`: `ChatProvider.stream(..., web_search: bool)`. New event `Citation(url, title)`. `Done` gains `web_searches: int | None`.
- `litellm_provider.py`: when `web_search` is true, pass `web_search_options` (Anthropic capped at 3 uses through `search_context_size` or the hosted tool's `max_uses`; Gemini uncapped by the vendor). Citations come from Anthropic `delta.provider_specific_fields["citation"]` and Gemini `annotations` (`url_citation`); only `http(s)` URLs, deduplicated. The cost includes web-search fees from LiteLLM's cost map (token cost + searches × the model's search price); unknown → `None`.
- Orchestrator: citations collected per turn; `TurnResult.sources` appends `{tool: "web", url, title}` after tool sources. Citations are **not** added to the verify pool (B4).
- `meta` frame gains `web_search: bool` (whether this model searched-capable for this turn).

## 5. Prompts (B1, B2, B7, B8)

- Recommendation format: lean and confidence **as returned by the stance tool**, reasons for and against from the tools, "what would change this view", data dates; news in words with no figures; never buy/sell/hold, never personal advice.
- Education allowed: general principles, no allocations, sizes or timing for the user.
- When the model cannot search: say news was not checked.
- New tool guidance: `company_performance`, `data_check`.

## 6. Education label (B8) — `verify.py` stays pure

- `ai/scope.py` (pure): `names_company(answer, tickers, names) -> bool` (word-boundary ticker match, case-sensitive; company names EN/AR normalised).
- Runner loads tickers/names once per turn (cached). If the answer names none of our companies **and** no successful company tool ran in this turn, the turn is answered with `general: true` and verification is skipped (`checked: 0`). Otherwise R49 verification applies.
- `answer` frame gains `general: bool`. Stored in `verification` as `{"general": true}`.

## 7. Frontend

- Types: `AssistantModel.web_search`, `meta.web_search`, `answer.general`, source `{tool: "web", url, title}`, cross-check types.
Owner UX rulings (2026-10-31):
- Model picker: capability as text inside the native option ("Claude Sonnet 5.5 · searches news").
- Answers: web sources as **chips after the data chips**, labelled with the site's domain, title on hover (`title`), opening in a new tab (`target=_blank rel="noopener noreferrer"`); `general` answers show "General information, not checked against our data"; a company-scoped answer from a model without search shows "News not checked with this model".
- Quality tab: a "Cross-checks" section **at the top of the tab** (overall status, one row per check with status pill, detail, evidence, methodology version, computed time, "Run checks now"). The cross-source row never shows a vendor value.
- **Explain button** on the Cross-checks section (card `data_check`; `/explain` accepts it, tool `data_check`).
- EN/AR copy, RTL, 375px, dark mode.

## 8. Addendum (owner rulings B15–B17, 2026-10-31)

- `ProviderError.code` adds `quota` (429 whose text says the quota is exceeded / RESOURCE_EXHAUSTED), distinct from `rate_limit`.
- The `error` frame gains `reason: "auth"|"rate_limit"|"quota"|"unavailable"|"bad_request"|"unknown"` when `code == "PROVIDER_ERROR"` (absent otherwise). `detail` names the model where useful and never says "try again" for `quota`.
- B15 fallback: when a call **with web search** fails with `quota` or `rate_limit` (or `bad_request` that mentions the search tool), the orchestrator retries the same call once without web search and records the provider in an in-process "search refused" map until the next UTC midnight; while recorded, search is not offered for that provider. The failed call adds no cost.
- `answer` and `unverified` frames gain `news: "searched" | "not_offered" | "unsupported" | "refused"`: `unsupported` = the model cannot search; `refused` = the provider refused search this turn or earlier today; `not_offered` = explain / no company question; `searched` = search was offered (whether or not the model used it). Replaces the frontend's use of `meta.web_search` for the note.
- Frontend: a provider error shows the reason-specific line as the main text (EN/AR), with the code under Details. Notes under an answer: `unsupported` → "News not checked with this model"; `refused` → "News not checked: the provider refused web search for this key". Cross-check rows render translated sentences and evidence labels (EN/AR) per check code, shares as %, dates localised; backend `detail` only for unknown codes.
