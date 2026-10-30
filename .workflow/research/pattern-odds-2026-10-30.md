# Chart-pattern odds on 5 years of EGX prices (2026-10-30)

Run: `python -m app.technical.pattern_backtest`, patterns-1.0, 199 companies, 239,184 stock-days, 2021-10-31 to 2026-10-29.

"Hit" = the price moved the expected way after h sessions (down for tops and descending/down-breaking patterns, up otherwise). "Base" = the share of all stock-days where the price moved that way over the same h. Interval = Wilson 95%.

| Pattern | h | n | hit % | base % | diff | Wilson 95% | median return |
|---|---|---|---|---|---|---|---|
| Head and shoulders top | 20 | 215 | 47.0 | 39.5 | +7.4 | 40.4-53.6 | +1.0% |
| Head and shoulders top | 60 | 196 | 38.3 | 33.4 | +4.9 | 31.7-45.2 | +5.1% |
| Inverse head and shoulders | 20 | 217 | 58.1 | 48.0 | +10.1 | 51.4-64.4 | +2.0% |
| Inverse head and shoulders | 60 | 210 | 65.2 | 58.1 | +7.2 | 58.6-71.4 | +9.2% |
| Double top | 20 | 537 | 39.9 | 39.5 | +0.3 | 35.8-44.0 | +2.1% |
| Double top | 60 | 515 | 38.6 | 33.4 | +5.2 | 34.5-42.9 | +5.5% |
| Double bottom | 20 | 697 | 55.7 | 48.0 | +7.7 | 52.0-59.3 | +2.3% |
| Double bottom | 60 | 675 | 60.4 | 58.1 | +2.4 | 56.7-64.1 | +6.7% |
| Ascending triangle | 20 | 128 | 53.1 | 48.0 | +5.2 | 44.5-61.6 | +1.9% |
| Ascending triangle | 60 | 119 | 68.1 | 58.1 | +10.0 | 59.2-75.8 | +9.5% |
| Descending triangle | 20 | 146 | 41.1 | 39.5 | +1.5 | 33.4-49.2 | +1.6% |
| Descending triangle | 60 | 138 | 42.0 | 33.4 | +8.6 | 34.1-50.4 | +4.1% |
| Symmetrical triangle, up break | 20 | 320 | 54.7 | 48.0 | +6.7 | 49.2-60.1 | +1.3% |
| Symmetrical triangle, up break | 60 | 312 | 63.5 | 58.1 | +5.4 | 58.0-68.6 | +6.2% |
| Symmetrical triangle, down break | 20 | 384 | 43.2 | 39.5 | +3.7 | 38.4-48.2 | +0.9% |
| Symmetrical triangle, down break | 60 | 366 | 40.4 | 33.4 | +7.0 | 35.5-45.5 | +4.6% |

## Reading
- Every pattern beats its base rate by 0 to 10 points; none is close to the 70-80% often quoted in trading books.
- Bearish patterns are right less than half the time (38-47%). After a "sell" pattern the median stock still rose (+1% to +5.5%), because EGX prices drifted up strongly over 2021-2026 (inflation and the devaluations).
- Clearest edges with an interval that clears the base rate: inverse head and shoulders (20 sessions), double bottom (20), ascending triangle (60).
- Double top at 20 sessions has no edge (+0.3 points).
- Cases overlap in time across stocks and within a stock, so the true uncertainty is wider than the Wilson interval shows.

## Forming shapes (patterns-1.1, R47 P6)

Measured from the session the shape became known (its last key point plus 5 sessions), before any breakout. Shapes still unresolved at the end of the data are left out. "Confirmed" = broke out in the expected direction within 20 sessions; "failed" = a close went the other way past it first; "expired" = neither within 20 sessions (or the triangle reached its apex).

| Shape | n | confirmed | failed | expired | 20-session hit vs base | 60-session hit vs base |
|---|---|---|---|---|---|---|
| Head and shoulders top | 344 | 63.1% | 21.2% | 15.7% | 46.6% vs 39.5% | 36.1% vs 33.4% |
| Inverse head and shoulders | 278 | 74.8% | 9.0% | 16.2% | 61.0% vs 48.0% | 67.7% vs 58.1% |
| Double top | 1,203 | 40.6% | 44.1% | 15.4% | 45.9% vs 39.5% | 38.1% vs 33.4% |
| Double bottom | 1,349 | 44.4% | 39.4% | 16.2% | 52.1% vs 48.0% | 62.2% vs 58.1% |
| Ascending triangle | 484 | 21.5% | 71.5% | 7.0% | 55.3% vs 48.0% | 64.4% vs 58.1% |
| Descending triangle | 610 | 19.3% | 73.1% | 7.5% | 42.6% vs 39.5% | 34.9% vs 33.4% |
| Symmetrical triangle | 1,273 | 46.0% (42.4% of breaks up) | n/a | 54.0% | no expected direction | no expected direction |

Reading: head-and-shoulders shapes usually complete (63-75%); double tops and bottoms complete less than half the time; triangles mostly fail (only ~20% of ascending/descending triangles break the expected way). Measured from the forming stage, the edge over an ordinary day is similar to or smaller than after a confirmed breakout.
