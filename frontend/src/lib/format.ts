/**
 * Single formatting module (merged from the former i18n/format.ts).
 *
 * Rules (ui-redesign-2026-10 section 2.6):
 * - every helper takes `locale` from `useLang()` as its first argument;
 * - digits stay Western in Arabic (`ar-EG-u-nu-latn`);
 * - a missing value (null, undefined, "", non-finite) returns `null`, and the
 *   caller renders `<Missing />`. Never "0", "NaN" or "Never";
 * - percent helpers take DECIMAL input (0.15 is 15.0%), never x100 twice.
 */

type Numeric = number | string | null | undefined;

const MINUS = "−";

/** Coerce an API number or decimal string; anything unusable becomes `null`. */
export function toNumber(value: Numeric): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "string" && value.trim() === "") return null;
  const n = typeof value === "string" ? Number(value) : value;
  return Number.isFinite(n) ? n : null;
}

function nf(locale: string, opts: Intl.NumberFormatOptions): Intl.NumberFormat {
  return new Intl.NumberFormat(locale, opts);
}

function fixed(locale: string, n: number, digits: number): string {
  return nf(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
}

/** Sign always shown (plus or U+2212 minus); zero carries no sign. */
function withSign(n: number, body: string): string {
  if (n > 0) return `+${body}`;
  if (n < 0) return `${MINUS}${body}`;
  return body;
}

/** Generic number formatter; non-numeric input is returned as text (legacy contract). */
export function fmtNum(locale: string, value: number | string, opts?: Intl.NumberFormatOptions): string {
  const n = toNumber(value);
  if (n === null) return String(value);
  return nf(locale, opts ?? {}).format(n);
}

/** Price: 2 dp always. 133.90 */
export function fmtPrice(locale: string, value: Numeric): string | null {
  const n = toNumber(value);
  return n === null ? null : fixed(locale, n, 2);
}

/** Absolute change and percent change (decimal): "−7.05 (−5.00%)". */
export function fmtChange(locale: string, abs: Numeric, pct: Numeric): string | null {
  const a = toNumber(abs);
  const p = toNumber(pct);
  if (a === null || p === null) return null;
  const absText = withSign(a, fixed(locale, Math.abs(a), 2));
  const pctText = withSign(p, `${fixed(locale, Math.abs(p) * 100, 2)}%`);
  return `${absText} (${pctText})`;
}

/** Decimal input, 1 dp fixed: 0.42 -> "42.0%". */
export function fmtPct(locale: string, value: Numeric): string | null {
  const n = toNumber(value);
  return n === null ? null : `${fixed(locale, n * 100, 1)}%`;
}

/** Decimal input, sign always: 0.631 -> "+63.1%", -0.143 -> "−14.3%". */
export function fmtSignedPct(locale: string, value: Numeric): string | null {
  const n = toNumber(value);
  if (n === null) return null;
  return withSign(n, `${fixed(locale, Math.abs(n) * 100, 1)}%`);
}

/** x-multiples, 2 dp: 1.18, 0.51. */
export function fmtRatio(locale: string, value: Numeric): string | null {
  const n = toNumber(value);
  return n === null ? null : fixed(locale, n, 2);
}

/** Grouped integer: 4,461,086. */
export function fmtInt(locale: string, value: Numeric): string | null {
  const n = toNumber(value);
  return n === null ? null : nf(locale, { maximumFractionDigits: 0 }).format(n);
}

/** Full EGP units divided by 1e6, 1 dp, grouped: 106,672.9. */
export function fmtEgpMillions(locale: string, value: Numeric): string | null {
  const n = toNumber(value);
  return n === null ? null : fixed(locale, n / 1e6, 1);
}

/** Compact EGP amounts: >=1e9 "bn" 2 dp, >=1e6 "m" 1 dp, else K. */
export function fmtEgpCompact(locale: string, value: Numeric): string | null {
  const n = toNumber(value);
  if (n === null) return null;
  const abs = Math.abs(n);
  const sign = n < 0 ? MINUS : "";
  const ar = locale.startsWith("ar");
  let body: string;
  if (abs >= 1e9) {
    body = ar ? `${fixed(locale, abs / 1e9, 2)} مليار` : `${fixed(locale, abs / 1e9, 2)}bn`;
  } else if (abs >= 1e6) {
    body = ar ? `${fixed(locale, abs / 1e6, 1)} مليون` : `${fixed(locale, abs / 1e6, 1)}m`;
  } else {
    body = ar ? `${fixed(locale, abs / 1e3, 0)} ألف` : `${fixed(locale, abs / 1e3, 0)}K`;
  }
  return ar ? `${sign}${body} ج.م` : `${sign}EGP ${body}`;
}

/** Composite stance score: signed integer, +40 / −20. */
export function fmtScore(locale: string, value: Numeric): string | null {
  const n = toNumber(value);
  if (n === null) return null;
  const r = Math.round(n);
  return withSign(r, nf(locale, { maximumFractionDigits: 0 }).format(Math.abs(r)));
}

function dateLocale(locale: string): string {
  return locale === "en" ? "en-GB" : locale;
}

/** Parse an ISO date or datetime; date-only strings are read as UTC. */
function parseIso(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "22 Oct 2026" / "22 أكتوبر 2026". */
export function fmtDate(locale: string, iso: string | null | undefined): string | null {
  const d = parseIso(iso);
  if (!d) return null;
  return new Intl.DateTimeFormat(dateLocale(locale), {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(d);
}

/** Cycle "2026-08" to month and year: "Aug 2026". */
export function fmtCycle(locale: string, cycle: string | null | undefined): string | null {
  if (!cycle || !/^\d{4}-\d{2}$/.test(cycle)) return null;
  const d = parseIso(`${cycle}-01`);
  if (!d) return null;
  return new Intl.DateTimeFormat(dateLocale(locale), {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(d);
}

export interface PluralForms {
  zero?: string;
  one?: string;
  two?: string;
  few?: string;
  many?: string;
  other: string;
}

/** Pick a plural form with `Intl.PluralRules(locale)`; "{n}" is replaced by the count. */
export function plural(locale: string, n: number, forms: PluralForms): string {
  const category = new Intl.PluralRules(locale).select(n);
  const template = (n === 0 ? forms.zero : undefined) ?? forms[category] ?? forms.other;
  return template.replace("{n}", fmtNum(locale, n));
}

// ─── Legacy helpers (callers outside the shell still import these) ────────

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Prices are decimal strings from the API; always render two decimals. */
export function formatPrice(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(2) : String(value);
}

export function formatVolume(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString();
}

/**
 * Render an as-of value. ISO datetimes use the locale; date-only strings are
 * rendered literally so a UTC midnight does not shift a day in local time.
 * Missing data is "—", never presented as fresh.
 */
export function formatAsOf(value: string | null | undefined): string {
  if (!value) return "—";
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (dateOnly) {
    const [, y, m, d] = dateOnly;
    return `${d} ${MONTHS[Number(m) - 1] ?? m} ${y}`;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
