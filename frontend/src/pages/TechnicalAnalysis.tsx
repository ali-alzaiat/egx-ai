import "./TechnicalAnalysis.css";

import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useCompanyByTicker, useCompanyPrices, useTechnicalIndicators, calculateIndicators } from '../api/client'
import CompanyNotFound from '../components/CompanyNotFound'

// Indicators are calculated from the stored price history the app already
// holds — the user never pastes prices by hand (F4).
export default function TechnicalAnalysis() {
  const { ticker } = useParams<{ ticker: string }>()
  const queryClient = useQueryClient()
  const { data: company, isLoading: companyLoading, error: companyError } = useCompanyByTicker(ticker)

  const { data: pricesData, isLoading: pricesLoading } = useCompanyPrices(company?.id, {
    page_size: 200,
  })

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

  // Oldest-first series for the context line; the API returns newest first.
  const series = useMemo(() => {
    const items = [...(pricesData?.items ?? [])].reverse()
    return {
      closes: items.map((p) => p.close),
      volumes: items.map((p) => String(p.volume)),
      firstDate: items.length > 0 ? items[0]!.date : null,
      lastDate: items.length > 0 ? items[items.length - 1]!.date : null,
    }
  }, [pricesData])

  const handleCalculate = async (): Promise<void> => {
    if (!company || series.closes.length === 0) return

    setIsCalculating(true)
    setError(null)

    try {
      const result = await calculateIndicators(
        company.id,
        series.closes.join(','),
        series.volumes.join(','),
      )
      setCalculationResult(result)
      await queryClient.invalidateQueries({ queryKey: ['technical'] })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to calculate indicators')
    } finally {
      setIsCalculating(false)
    }
  }

  if (companyLoading) {
    return <div className="loading">Loading company...</div>
  }

  if (companyError || !company) {
    return <CompanyNotFound ticker={ticker} />
  }

  const rows = calculationResult?.indicators ?? []

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Technical Analysis — {company.ticker}</h2>
          <p className="subtitle">{company.name}</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleCalculate}
          disabled={isCalculating || pricesLoading || series.closes.length === 0}
        >
          {isCalculating ? 'Calculating…' : 'Calculate indicators'}
        </button>
      </div>


      {pricesLoading && <div className="loading">Loading price history...</div>}
      {!pricesLoading && series.closes.length === 0 && (
        <p className="muted">No price data from the configured source for {company.ticker}.</p>
      )}
      {series.closes.length > 0 && (
        <p className="muted">
          Calculated from the last {series.closes.length} trading days of stored
          price history ({series.firstDate} – {series.lastDate}).
        </p>
      )}

      {error && (
        <div className="alert alert-error">
          {error}{' '}
          <button className="link-btn" onClick={handleCalculate}>
            Retry
          </button>
        </div>
      )}

      {rows.length > 0 && (
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
                {rows.map((ind) => (
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

      <div className="card">
        <h3 style={{ marginBottom: '1rem' }}>Previously Calculated Indicators</h3>
        {loadingIndicators ? (
          <div className="loading">Loading indicators...</div>
        ) : existingIndicators && existingIndicators.length > 0 ? (
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
        ) : (
          <p className="muted">No indicators calculated yet.</p>
        )}
      </div>
    </div>
  )
}
