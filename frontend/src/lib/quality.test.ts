import { describe, expect, it } from 'vitest'
import { qualityLabelKey, qualityTone } from './quality'

describe('qualityTone', () => {
  it('maps OK to positive', () => {
    expect(qualityTone('OK')).toBe('positive')
  })

  it('maps DEGRADED to warning', () => {
    expect(qualityTone('DEGRADED')).toBe('warning')
  })

  it('maps POOR to negative', () => {
    expect(qualityTone('POOR')).toBe('negative')
  })

  it('maps MISSING to muted', () => {
    expect(qualityTone('MISSING')).toBe('muted')
  })

  it('falls back to muted for an unknown status', () => {
    expect(qualityTone('SOMETHING_ELSE')).toBe('muted')
  })
})

describe('qualityLabelKey', () => {
  it('maps each status to its copy key', () => {
    expect(qualityLabelKey('OK')).toBe('fn_dq_band_good')
    expect(qualityLabelKey('DEGRADED')).toBe('fn_dq_band_partial')
    expect(qualityLabelKey('POOR')).toBe('fn_dq_band_poor')
    expect(qualityLabelKey('MISSING')).toBe('fn_dq_band_missing')
  })

  it('falls back to the unknown key for an unknown status', () => {
    expect(qualityLabelKey('SOMETHING_ELSE')).toBe('fn_dq_band_unknown')
  })
})
