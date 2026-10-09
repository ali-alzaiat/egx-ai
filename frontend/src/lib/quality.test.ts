import { describe, expect, it } from 'vitest'
import { qualityLabel, qualityTone } from './quality'

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

describe('qualityLabel', () => {
  it('maps OK to Good', () => {
    expect(qualityLabel('OK')).toBe('Good')
  })

  it('maps DEGRADED to Partial', () => {
    expect(qualityLabel('DEGRADED')).toBe('Partial')
  })

  it('maps POOR to Poor', () => {
    expect(qualityLabel('POOR')).toBe('Poor')
  })

  it('maps MISSING to Insufficient data', () => {
    expect(qualityLabel('MISSING')).toBe('Insufficient data')
  })

  it('falls back to Unknown for an unknown status', () => {
    expect(qualityLabel('SOMETHING_ELSE')).toBe('Unknown')
  })
})
