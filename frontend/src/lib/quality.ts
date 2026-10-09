import type { DataQualityStatus } from '../types'

export type QualityTone = 'positive' | 'warning' | 'negative' | 'muted'

/** The only place a data-quality status maps to a colour tone. Unknown → muted. */
export function qualityTone(status: DataQualityStatus | string): QualityTone {
  switch (status) {
    case 'OK':
      return 'positive'
    case 'DEGRADED':
      return 'warning'
    case 'POOR':
      return 'negative'
    default:
      // MISSING and anything unexpected are neutral, never red.
      return 'muted'
  }
}

/** The only place a data-quality status maps to its badge word. */
export function qualityLabel(status: DataQualityStatus | string): string {
  switch (status) {
    case 'OK':
      return 'Good'
    case 'DEGRADED':
      return 'Partial'
    case 'POOR':
      return 'Poor'
    case 'MISSING':
      return 'Insufficient data'
    default:
      return 'Unknown'
  }
}
