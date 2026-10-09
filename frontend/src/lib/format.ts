/** Display helpers for prices, volumes and as-of dates (F11/F17). */

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

/** Prices are decimal strings from the API; always render two decimals. */
export function formatPrice(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  return Number.isFinite(n) ? n.toFixed(2) : String(value)
}

export function formatVolume(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString()
}

/**
 * Render an as-of value. ISO datetimes use the locale; date-only strings are
 * rendered literally so a UTC midnight does not shift a day in local time.
 * Missing data is "Never", never presented as fresh.
 */
export function formatAsOf(value: string | null | undefined): string {
  if (!value) return 'Never'
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (dateOnly) {
    const [, y, m, d] = dateOnly
    return `${d} ${MONTHS[Number(m) - 1] ?? m} ${y}`
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
