import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useCompanyByTicker, useTechnicalIndicators, calculateIndicators } from '../api/client'

const INDICATOR_TYPES = ['sma', 'ema', 'rsi', 'macd', 'bollinger', 'obv', 'vwap']

export default function TechnicalAnalysis() {
  const { ticker } = useParams<{ ticker: string }>()
  const { data: company, isLoading: companyLoading } = useCompanyByTicker(ticker)

  const [prices, setPrices] = useState('')
  const [volumes, setVolumes] = useState('')
  const [selectedTypes, setSelectedTypes] = useState<string[]>(INDICATOR_TYPES)
  const [isCalculating, setIsCalculating] = useState(false)
  const [calculationResult, setCalculationResult] = useState<null | {
    indicators: {
      indicator: string
      value: string | null
      status: string
      parameters: Record<string, unknown> | null
      reason: string | null
    }[]
    calculated_at: string
  }>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: existingIndicators, isLoading: loadingIndicators } = useTechnicalIndicators(company?.id)

  const handleCalculate = async () => {
    if (!company) return

    setIsCalculating(true)
    setError(null)

    try {
      const result = await calculateIndicators(
        company.id,
        prices,
        volumes,
        selectedTypes.join(','),
      )
      setCalculationResult(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to calculate indicators')
    } finally {
      setIsCalculating(false)
    }
  }

  const toggleType = (type: string) => {
    setSelectedTypes((prev) =>
      prev.includes(type)
        ? prev.filter((t) => t !== type)
        : [...prev, type],
    )
  }

  if (companyLoading) {
    return <div className="loading">Loading company...</div>
  }

  if (!company) {
    return <div className="error">Company not found</div>
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Technical Analysis — {company.ticker}</h1>
        <p style={{ color: 'var(--text-secondary)' }}>{company.name}</p>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ marginBottom: '1rem' }}>Calculate Indicators</h3>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
          Enter comma-separated historical prices and volumes to calculate technical indicators.
        </p>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>
            Prices (comma-separated)
          </label>
          <input
            type="text"
            value={prices}
            onChange={(e) => setPrices(e.target.value)}
            placeholder="e.g. 10.5, 11.2, 10.8, 11.5, 12.0"
            style={{ width: '100%', padding: '0.5rem', boxSizing: 'border-box' }}
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>
            Volumes (comma-separated)
          </label>
          <input
            type="text"
            value={volumes}
            onChange={(e) => setVolumes(e.target.value)}
            placeholder="e.g. 1000, 1500, 1200, 1800, 2000"
            style={{ width: '100%', padding: '0.5rem', boxSizing: 'border-box' }}
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>
            Indicators
          </label>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {INDICATOR_TYPES.map((type) => (
              <label
                key={type}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={selectedTypes.includes(type)}
                  onChange={() => toggleType(type)}
                />
                {type.toUpperCase()}
              </label>
            ))}
          </div>
        </div>

        {error && (
          <div style={{ color: 'var(--color-negative)', marginBottom: '1rem' }}>
            {error}
          </div>
        )}

        <button
          className="btn btn-primary"
          onClick={handleCalculate}
          disabled={isCalculating || !prices || !volumes}
        >
          {isCalculating ? 'Calculating...' : 'Calculate Indicators'}
        </button>
      </div>

      {calculationResult && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>Calculated Indicators</h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Indicator</th>
                  <th>Value</th>
                  <th>Status</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {calculationResult.indicators.map((ind) => (
                  <tr key={ind.indicator}>
                    <td>{ind.indicator.toUpperCase()}</td>
                    <td>{ind.value || '--'}</td>
                    <td className={ind.status === 'AVAILABLE' ? 'positive' : 'negative'}>
                      {ind.status}
                    </td>
                    <td>{ind.reason || '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {existingIndicators && existingIndicators.length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: '1rem' }}>Previously Calculated Indicators</h3>
          {loadingIndicators ? (
            <div className="loading">Loading indicators...</div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Value</th>
                    <th>Status</th>
                    <th>Calculated At</th>
                  </tr>
                </thead>
                <tbody>
                  {existingIndicators.map((ind) => (
                    <tr key={ind.id}>
                      <td>{ind.indicator_type.toUpperCase()}</td>
                      <td>{ind.value || '--'}</td>
                      <td className={ind.status === 'AVAILABLE' ? 'positive' : 'negative'}>
                        {ind.status}
                      </td>
                      <td>{new Date(ind.calculated_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
