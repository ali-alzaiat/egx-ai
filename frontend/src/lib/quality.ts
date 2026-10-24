import type { CopyKey } from '../i18n'
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

/** The only place a data-quality status maps to its word; the caller translates the key. */
export function qualityLabelKey(status: DataQualityStatus | string): CopyKey {
  switch (status) {
    case 'OK':
      return 'fn_dq_band_good'
    case 'DEGRADED':
      return 'fn_dq_band_partial'
    case 'POOR':
      return 'fn_dq_band_poor'
    case 'MISSING':
      return 'fn_dq_band_missing'
    default:
      return 'fn_dq_band_unknown'
  }
}
