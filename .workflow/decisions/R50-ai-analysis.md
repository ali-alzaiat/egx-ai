# R50 AI analysis: performance, research lean, news, education, data cross-checks

Owner request (2026-10-31): the assistant should analyse a company's performance, give a recommendation
based on the data and current events, give general advice about stocks, and verify whether the app's
data is true. Builds on R49 (branch `ai-analysis` on top of `ai-assistant`).

| # | Decision | Owner's choice |
|---|---|---|
| B1 | Recommendation form | **Research lean** (leans buy / neutral / leans reduce) with confidence, reasons for and against, what would change it, and data dates. AGENTS.md rule 10 unchanged. |
| B2 | Where the lean comes from | **Stance engine only** (signal-rules-2.0, as on the Price tab). The AI explains it; news is "may change this view" context in words and never overrides the lean. |
| B3 | Current events | **The model vendor's own web search** through LiteLLM `web_search_options` (Claude Sonnet/Opus, Gemini). |
| B4 | News figures and the number check | **News in words only.** Every figure must still match our tool data; a web figure fails `verify()`. News citations (URL, title) are sources, built from the vendor's citation metadata, never from model text. |
| B5 | Models without web search (OpenAI chat models, Claude Haiku 4.5 in LiteLLM 1.105.1) | **Answer without news**, saying news was not checked with this model; the model picker marks search-capable models. |
| B6 | When to search | **The model decides, capped**: at most 3 searches per answer where the vendor allows a cap; search fees are added to the turn's cost and the monthly cap applies (free tier still skips it). |
| B7 | General advice | **Education only**: general principles, no advice about the user's own money (allocation, position size, timing). |
| B8 | Numbers in education answers | **Label, but check companies**: an answer that names no company of ours (ticker or name, matched in code) is labelled "General information, not checked against our data" and its figures are not checked; an answer naming any of our companies is checked as in R49. |
| B9 | Performance | A deterministic `company_performance` tool: returns over 1M/3M/6M/YTD/1Y and revenue / net income TTM and YoY with margins, all computed in code. |
| B10 | Benchmark | **EGX30** (`^CASE30` from Yahoo) added to the daily price sync; performance reports stock and index returns side by side. |
| B11 | Data cross-checks | Deterministic checks in code (provenance, cross-source, accounting identities, price sanity, freshness), **run after each sync and when facts land**, stored with a methodology version, shown in a "Cross-checks" section of the company Quality tab and read by the assistant through a `data_check` tool. |
| B12 | Grading vendor-only statements (real-data check: 205 of 234 failed overall) | **Vendor-only = warn** ("not confirmed by a filing"); fail stays for evidence of wrong data, and for lines with no source at all. |
| B13 | EGX one-day price limit in `price_sanity` | **20%** (halt at 10%, then up to 20% in the day; matches the stored history). Owner to confirm against current EGX rules. |
| B14 | Benchmark when Yahoo has no EGX30 history (`^CASE30` returns only the latest day) | **Build up EGX30 daily** (official closes stored each sync; a window is INSUFFICIENT_DATA until covered) **plus the sector peer median** return per window from stored prices (at least 5 peers, else INSUFFICIENT_DATA), labelled with the peer count. |
| B15 | Provider refuses web search (verified: a free Gemini key has no grounding quota; plain and tool calls work) | **Fall back and remember**: retry the call once without search, answer from our data with a "provider refused web search" note, and skip search for that provider until the next UTC day (in-process). |
| B16 | Provider error display | **Reason up front**: the main line says what happened and what to do, per reason (auth, rate limit, quota, unavailable, refused request); a quota refusal never says "try again shortly". |
| B17 | Cross-check wording | **Translated in the UI** (EN/AR) from check codes and evidence numbers; backend `detail` is the fallback for unknown checks. |

Not in scope: buy/sell labels, personal portfolio advice, OpenAI web search through the Responses API,
fetching any vendor page. Vendor files stay offline; the UI never shows a vendor figure (only an
agreement band).
