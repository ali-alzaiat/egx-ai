# Research: Data-quality / coverage / confidence UX patterns

**Question:** How do competitor platforms visually present data quality / coverage / confidence to retail users — layout, color, missing-data wording, component shape, score display?
**Researcher:** nadia (via router) · 2026-10-09 · all URLs fetched 2026-10-09. UI/UX layer on top of `task-5-data-quality-scoring.md`.

## What the market ships

**Simply Wall St — "Snowflake" (most-imitated retail pattern).** 5-axis radar; each axis carries 6 checks shown as `x/6`; snowflake size = checks passed, colour shifts green→red with fewer checks. Score block sits near the top of the company page under "Stock Overview". A "Data | Last Updated (UTC)" table lists per-item freshness + a Data Sources link. Honest-limits copy: a low score "should not necessarily exclude a stock."
- https://github.com/SimplyWallSt/Company-Analysis-Model/blob/master/MODEL.markdown
- https://simplywall.st/stocks/mx/software/bmv-snow/snowflake-shares
- https://simplywall.st/stocks/us/software/nyse-snow/snowflake

**SteadyShares — "data quality score" 0–100 (closest precedent).** "share of a company's model inputs that were actually available from filings and market data." Explained in one sentence next to the numbers: "A low score means the rating, moat and fair value stand on fewer legs; the interface says so next to the numbers rather than pretending confidence." Missing data "renders as nothing, never as zero, and never as an estimate dressed up as a fact." Suppression: "Below a quality floor, the product refuses to state a verdict at all." Freshness: "an undated figure in finance is an unusable one"; quotes timestamped UTC; stale marked stale.
- https://steadyshares.com/methodology
- https://steadyshares.com/stocks/FMX
- https://steadyshares.com/about

**FoudaLens (EGX-local) 0–100.** Score in the page subtitle under the H1 + "Last updated" date + band label ("Positive band"). "Prices are not real-time. Subscribe to Premium for real-time quotes." Footer: "Prices may not be 100% accurate, verify with official sources before making investment decisions." Score is technical-only; weights published.
- https://foudalens.com/en/stock/HDBK.CA
- https://foudalens.com/en/screener
- https://foudalens.com/en/about
- https://foudalens.com/en/methodology

**Mubasher (EGX-local) freshness.** Delay notice: "All data are 15 minutes late during market session." Each ratio carries provenance on the same line: `Book Value (BVPS) 30.62 … Based on: Third Quarter 2025`, `P/B Ratio 7.30 · Last update: 2026-05-08`.
- https://english.mubasher.info/markets/EGX/indices/EGX30
- https://english.mubasher.info/markets/egx/stocks/EFIC

**Morningstar "Data Coverage %" (institutional).** "the extent to which underlying data inputs were available … at the time of the rating assignment." Shown as a plain figure beside pillar scores; weight-scaled and auditable (26/28 People points = 92.9% → overall 96.9%). Retail placement: no data.
- https://www.morningstar.com/investing-terms/data-coverage-
- https://lt.morningstar.com/1c6qh1t6k9/snapshotresearchpdf/default.aspx?Id=0P0001NTTO
- https://s205.q4cdn.com/437373358/files/doc_downloads/2025/03/25/1227010-42.pdf

**Koyfin.** Freshness documented in help text, not a per-stock badge; timestamp on hover over the ticker or in the quote box.
- https://www.koyfin.com/help/faq/is-your-data-live-or-delayed
- https://www.koyfin.com/help/data-overview

**GetData (vendor coverage report).** `Coverage % = (available valid ÷ expected) × 100`; table `Year | Coverage % | Gap % | Expected | Present | Missing`; weekends/holidays excluded from denominator.
- https://getdata.finance/coverage/es (cached; live returned 530)

**Measurabl Data Completeness.** Donut charts for portfolio metrics, then sortable building cards, with tooltips defining each metric.
- https://support.measurabl.com/hc/en-us/articles/4409422922381-Data-Completeness-101

**Soda.** Health score = % checks passed; three states pass/warn/fail; drill down health → dataset → column → check → trend; API exposes dataset health and coverage separately.
- https://docs.soda.io/manage-issues
- https://soda.io/blog/soda-introduces-new-reporting-api

**Kyro (best wording precedent for "limited/missing").** State `DATA_LIMITED`: "means Kyro has limited data coverage or confidence for this wallet. It does not mean the wallet is bad." / "missing evidence is not guilt." Coverage notes are advisory, "never change the verdict," "visible instead of silent." "Kyro reports nothing instead of guessing."
- https://docs.thekyro.co/data-coverage

## Cross-cutting answers

- **Layout:** near the top of the company page as a trust qualifier on the figures below; plus drill-down (one headline score, then per-component detail). No precedent for a lone unexplained number.
- **Color:** green/amber/red (RAG) is de-facto for status. Missing is best its own neutral state, not red and not zero.
  - https://www.gov.uk/government/publications/water-and-sewerage-companies-epa-methodology-for-2026-to-2030/3-rag-thresholds-for-epa-metrics
  - https://ico.org.uk/media2/q1ebmblw/20250331-q3-ico25-scorecard-v1-0-mb.pdf
- **Wording:** pair the caveat with an action ("verify with official sources", "see what's missing"); avoid false precision (no raw 0.73).
  - https://medium.com/@Modexa/the-confidence-ui-pattern-that-users-actually-trust-ff27e1a8a956
- **Component shapes:** radar `x/6`, donut, plain `NN%`/`NN/100`, Expected/Present/Missing tables, pass/warn/fail. A literal progress-bar meter is a design choice, not a financial-retail convention.
- **Score display:** a number + a word, always with a legend/breakdown. Bare gauge/badge without legend is an anti-pattern.
  - https://www.aiuxplayground.com/pattern/confidence-indicators
  - https://agenticuxpatterns.com/patterns/confidence-thermometer
- **Accessibility (must):** never encode status by color alone — color + icon + text. ~8% of men are red–green color-blind.
  - https://thefrontkit.com/docs/trading-dashboard-kit/accessibility
  - https://grafana.com/blog/3-tips-to-improve-your-grafana-dashboard-design/
  - https://www.gooddata.ai/docs/cloud/create-dashboards/accessibility
  - https://developer.android.com/stories/apps/futu

## Gaps (`no data`)

No EGX-local vendor publishes a DQ score; no per-stock retail DQ badge (closest = SteadyShares text score, Morningstar institutional); Morningstar 67% gate not re-found here; exact color hex tokens none; Bloomberg/FactSet/Refinitiv retail DQ UI; SteadyShares on-page widget position; Mubasher "commercial companies only… quarterly" not re-found; getdata live (530).

## Recommendations for our card (inputs to ux-expert)

1. **Placement:** high on the company page as a qualifier to the figures below — not a footer note.
2. **Headline = number + word + scale:** `NN/100` plus a band label plus a one-line definition ("share of model inputs available from filings"). Never a bare gauge. No false-precision decimals.
3. **Show the component breakdown**, not just the headline (per-component coverage with counts).
4. **Color green/amber/red for quality bands**, cut-offs documented, and never color alone — pair with icon + text label.
5. **Missing ≠ zero ≠ red.** Neutral state worded as limited coverage, not bad data ("Insufficient data — not a judgment on the company").
6. **Suppress the verdict below a floor** rather than showing a low score; say why (aligns with AGENTS.md INSUFFICIENT_DATA).
7. **Show freshness + provenance as visible fields:** as-of period + last-updated date + source line.
8. **Caveat + action**, not caveat alone ("see what's missing").
9. **Keep copy short and concrete.**
10. **Layout:** a labelled number + small per-component bars/rows, or a ring with the number centred; both are supported precedents.
