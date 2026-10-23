# R42 — signal-rules-2.0 + official EGX33 Shariah membership

**Date:** 2026-10-23
**Trigger:** User-approved reprioritization after the ZBorsa competitive review: recommendations and Shariah first, payments deferred. Resolves the R41 open ruling ("BUY stance is unreachable under the fixed rubric").

## Ruling 1: stance methodology moves to signal-rules-2.0

**Defect in v1:** missing engines scored 0. With no fundamentals in the database (0 financial facts), the best possible total was +20, below the 35 HOLD floor. Every stock was `reduce`, and BUY (≥60) was unreachable even with every engine bullish (max 55).

**v2** (`app/signals/rules.py`, pure; `app/signals/stance.py`, I/O):
- The composite is a weighted mean over the engines that produced an input (technical 40 / valuation 35 / score 25), scaled to [-100, 100]. BUY ≥ 25, REDUCE ≤ −25, otherwise HOLD.
- Missing engines lower confidence through coverage, never the stance. Confidence caps: technical-only 50, low liquidity 30, statements older than 400 days 40.
- The technical sub-score is the mean of votes: price vs SMA50 (SMA20 if history is short), SMA50 vs SMA200, RSI14 (overbought and oversold get 0), MACD line sign, 20-session momentum (±5% band). Volume surges are explained but carry no vote.
- Reference levels: an ATR14 band around the last close (+2 ATR upside, −1.5 ATR downside), labelled a volatility reference, not a forecast. The stop falls back from entry % to ATR downside, then to the range low.
- Liquidity gate: a 20-session average value traded below EGP 500K raises a LOW LIQUIDITY flag (Phase 10/14 rule).
- **Shariah leaves the score.** v1 subtracted 30 for non-compliance; compliance is a filter, not a return signal. It is now its own block (`app/screening/status.py`).

**Sanity check on real prices (2026-10-22 close, 50 most-traded names):** 4 buy / 4 hold / 42 reduce. This matches the market: median 20-session change was −14.3% and 88% of the names were down, while the long-term trend was still up for 45 of 50. AMOC: BUY, entry 13.51, downside 12.61. ZBorsa publishes the same entry and stop (their target is 14.87; our ATR upside is 14.71).

**Not yet validated:** there is no backtest of v2 (Phase 10 / roadmap item 4). Confidence stays low by construction until fundamentals and a track record exist.

## Ruling 2: official EGX33 Shariah membership is loaded as data

- Source: `https://www.egx.com.eg/en/currentindexconstituntes.aspx?type=22&nav=22`, read 2026-10-23 in a browser. robots.txt was empty; plain HTTP clients get their connection reset, and no CAPTCHA or auth was involved.
- 34 lines (33 companies; FAIT has EGP and USD lines), all matched to our tickers. They are stored as `screening_egx_memberships` for cycle `2026-08` via `python -m app.screening.egx33`.
- **Unreconciled:** the page carries no effective date, and EGX's Sep-2026 review press release lists CLHO and GOUR as deletions while the page still lists them. This is recorded in each row's note; re-check at the next review.
- Per R32 B5, membership is shown beside our verdict and never overrides it. Absence from EGX33 is labelled "not a non-compliance verdict".

## Surfaces

- `GET /api/stance/radar` now ranks the most-traded companies (30-day average value traded). It supports `shariah=egx33` and returns name, score, price, reference levels, low_liquidity and shariah.
- `GET /api/stance/companies/{ticker}` adds score, coverage, reference_levels, liquidity and shariah.
- Frontend: new `/recommendations` page (radar with Shariah-only toggle and stance filter), and the Signals tab shows levels, liquidity and the Shariah block.
