/**
 * Locale-aware number formatting.
 * Digits stay Latin even in Arabic (`ar-EG-u-nu-latn`) — matches API data.
 */
export function fmtNum(locale: string, value: number | string, opts?: Intl.NumberFormatOptions): string {
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n)) return String(value);
  return new Intl.NumberFormat(locale, opts).format(n);
}

/** Percent-style ratios stored as decimals (0.15 -> 15%). */
export function fmtPct(locale: string, value: number | string | null): string {
  if (value === null) return "—";
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 1 }).format(n);
}
