import { useMemo } from "react";
import { useCompanyPrices, useDataSources } from "../../api/client";
import { toNumber } from "../../lib/format";
import type { ChartBar } from "../../lib/priceChart";
import { priceSourceLabel } from "../../lib/priceSource";
import type { DailyPrice } from "../../types";

/** Placeholder bars (O=H=L=C and zero volume) are not trading days. */
export function isPlaceholderBar(p: DailyPrice): boolean {
  return p.open === p.high && p.high === p.low && p.low === p.close && p.volume === 0;
}

/** Real trading-day bars, newest first. */
export function realBarsNewestFirst(items: readonly DailyPrice[]): DailyPrice[] {
  return items
    .filter((p) => !isPlaceholderBar(p))
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
}

/** Ascending close series for the chart. */
export function chartBars(newestFirst: readonly DailyPrice[]): ChartBar[] {
  const out: ChartBar[] = [];
  for (let i = newestFirst.length - 1; i >= 0; i--) {
    const bar = newestFirst[i]!;
    const close = toNumber(bar.close);
    if (close !== null) out.push({ date: bar.date, close });
  }
  return out;
}

/** Lowest low and highest high over the bars; null when there are none. */
export function fiftyTwoWeekRange(bars: readonly DailyPrice[]): { low: number; high: number } | null {
  let low = Infinity;
  let high = -Infinity;
  for (const b of bars) {
    const l = toNumber(b.low);
    const h = toNumber(b.high);
    if (l !== null) low = Math.min(low, l);
    if (h !== null) high = Math.max(high, h);
  }
  return Number.isFinite(low) && Number.isFinite(high) ? { low, high } : null;
}

/**
 * One year of daily bars: the same query (and cache entry) the hub header
 * uses, so the Overview and Price tabs add no request.
 */
export function useYearPrices(companyId: string | undefined) {
  const startDate = useMemo(() => {
    const d = new Date();
    d.setFullYear(d.getFullYear() - 1);
    return d.toISOString().split("T")[0]!;
  }, []);
  const query = useCompanyPrices(companyId, { start_date: startDate, page_size: 300 });
  const sources = useDataSources();
  const bars = useMemo(() => realBarsNewestFirst(query.data?.items ?? []), [query.data]);
  const series = useMemo(() => chartBars(bars), [bars]);
  const sourceId = bars[0]?.source_id;
  const source = priceSourceLabel(sources.data?.find((s) => s.id === sourceId)?.name);
  return { query, bars, series, latest: bars[0], source };
}
