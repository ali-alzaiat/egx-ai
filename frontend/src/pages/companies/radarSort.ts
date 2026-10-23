// Pure sorting helper for the Companies radar table (Task 12).
// No React, no I/O — safe for unit tests and memoized reuse.

export type RadarSortValue = string | number | null

export type RadarSortDir = "asc" | "desc"

/** Row shape requirement: any object; the key is read dynamically. */
export type RadarRowLike = object

export type RadarSortKey = string

/** Anything null-ish or an empty string is a blank; blanks never compare, they push to the end. */
function isBlank(value: unknown): boolean {
  return value === null || value === undefined || value === ""
}

const NUMERIC_PATTERN = /^-?\d+(?:\.\d+)?$/

/** Numeric strings ("9.5") must compare numerically, not lexicographically. */
function isNumericString(value: string): boolean {
  return NUMERIC_PATTERN.test(value)
}

function compareValues(a: unknown, b: unknown): number {
  if (typeof a === "number" && typeof b === "number") {
    return a - b
  }
  if (typeof a === "string" && typeof b === "string") {
    if (isNumericString(a) && isNumericString(b)) {
      return Number.parseFloat(a) - Number.parseFloat(b)
    }
    return a.localeCompare(b)
  }
  // Mixed (number vs string): compare their string forms; numbers that were
  // numeric strings are normalized to the same form first.
  const normalize = (v: unknown): string => {
    if (typeof v === "number") {
      return String(v)
    }
    if (typeof v === "string" && isNumericString(v)) {
      return String(Number.parseFloat(v))
    }
    return String(v)
  }
  return normalize(a).localeCompare(normalize(b))
}

/**
 * Stable sort of radar rows by one column.
 * - Blank cells (null / undefined / "") always sort last in BOTH directions.
 * - Numeric-string values compare numerically ("9.5" < "10").
 * - Ascending by default; the input array is never mutated.
 */
export function sortRadarRows<T extends RadarRowLike>(
  rows: readonly T[],
  key: RadarSortKey,
  dir: RadarSortDir = "asc",
): T[] {
  const read = (row: T): unknown => {
    const holder = row as Record<string, unknown>
    return holder[key]
  }
  return [...rows].sort((a, b) => {
    const av = read(a)
    const bv = read(b)
    if (isBlank(av) && isBlank(bv)) return 0
    if (isBlank(av)) return 1
    if (isBlank(bv)) return -1
    const cmp = compareValues(av, bv)
    return dir === "desc" ? -cmp : cmp
  })
}
