# R51 contract: stance reason codes, panel push, answer text, encoding

Rulings: `.workflow/decisions/R51-demo-fixes.md`. Display-only: no threshold, weight or rule change,
so `signal-rules` stays at its current version.

## 1. Stance reason parts (C1), `GET /api/stance/companies/{ticker}`

`reasons[]` items gain `parts: [{code, params}]`, one per sentence in `text`, same order; `params`
values are strings exactly as the English text prints them. `text` is unchanged.

| engine | code | params | English today |
|---|---|---|---|
| technical | `trend` | `side`: above/below/at, `ma`: SMA50/SMA20 | "Price below SMA50." |
| technical | `long_trend` | `side`: above/below/at | "SMA50 below SMA200." |
| technical | `rsi` | `value`, `state`: overbought/oversold/above_50/below_50 | "RSI 37.88 below 50." |
| technical | `macd` | `side`: positive/negative/flat | "MACD line negative (EMA12 vs EMA26)." |
| technical | `momentum` | `direction`: up/down/flat, `pct` (as printed: unsigned for up/down, signed for flat) | "Flat (-4.6%) over 20 sessions." |
| volume | `volume_unusual` | `ratio` | "Unusual volume: 1.8x the 20-session average." |
| valuation | `fair_value_vs_market` | `ratio`, `market_ratio`, `peers`, `confidence`: High/Medium/Low, `subscore` | "Price is 0.88x fair value vs a market median of 2.60x (118 companies, High confidence): sub-score +1.00." |
| valuation | `scenario_range` | `subscore` | "Price vs scenario range: sub-score +0.5." |
| score | `investment_score` | `headline`, `subscore` | "Investment score 62: sub-score +0.24." |

New field `limitation_items: [{code, params, text}]`, same order and length as `limitations`
(which stays as is):

| code | params |
|---|---|
| `compliance_footer` | — |
| `statement_freshness_unknown` | — |
| `statement_stale` | `days`, `max_days` |
| `low_liquidity` | `min_egp`, `window` |
| `no_engine_input` | — |
| `technical_only` | — |
| `missing_inputs` | `inputs`: comma-separated of `technical`, `valuation`, `score` (the English text keeps its parenthetical notes) |
| `levels_band` | — |
| `stop_reference` | — |

Stored or older payloads without `parts` / `limitation_items` render the English `text` (in a `lang="en"` span).

## 2. Frontend

- Price & signals "Why" and "Limitations", and the Overview "At a glance" stance line: render each
  part from EN/AR copy keyed by code (+ `side`/`state`/`direction` variants), numbers with the
  locale formatter; unknown code or missing parts → the English text. `visibleLimitations` keeps
  dropping the footer, the levels band and stop copy (by code when present).
- Assistant panel (C2): at `min-width: 1280px`, while the panel is open, the main column gets
  `padding-inline-end: 420px` (logical, so RTL pushes from the left); below 1280 px it stays an overlay.
- Answer text: a pair of backticks renders its content as plain text (no backticks shown).
- Recommendations: no counts or "0 stocks" while loading (done).

## 3. Backend

- `ingestion/egx/universe.py`: a response with no charset in `Content-Type` is decoded as UTF-8
  (helper with a unit test; never Latin-1 by default).
- Prompt `assistant-1.3`: plain words only in answers: no backticks, no tool names or check
  codes (say "the performance data", "the price sanity check"), statuses as words (warning, passed,
  not enough data). Still name the source in plain words.
