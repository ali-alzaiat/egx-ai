import "./ShariahScreening.css";

import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { screenCompany, useCompanyByTicker, useScreeningResult } from '../api/client'
import { formatAsOf } from '../lib/format'
import CompanyNotFound from '../components/CompanyNotFound'
import CompanyTabs from '../components/CompanyTabs'

function verdictBadge(status: string): { label: string; className: string } {
  if (status === 'COMPLIANT') return { label: 'Compliant', className: 'healthy' }
  if (status === 'NON_COMPLIANT') return { label: 'Not compliant', className: 'error' }
  return { label: 'Not enough data', className: 'unknown' }
}

export default function ShariahScreening() {
  const { ticker } = useParams<{ ticker: string }>()
  const queryClient = useQueryClient()
  const { data: company, isLoading: companyLoading, error: companyError } = useCompanyByTicker(ticker)
  const {
    data: result,
    isLoading: resultLoading,
    error: resultError,
    refetch,
  } = useScreeningResult(company?.id)

  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  const handleScreen = async (): Promise<void> => {
    if (!company) return
    setRunning(true)
    setRunError(null)
    try {
      await screenCompany(company.id)
      await queryClient.invalidateQueries({ queryKey: ['screening'] })
      await refetch()
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Screening failed')
    } finally {
      setRunning(false)
    }
  }

  if (companyLoading || resultLoading) {
    return <div className="loading">Loading company...</div>
  }

  if (companyError || !company) {
    return <CompanyNotFound ticker={ticker} />
  }

  const badge = result ? verdictBadge(result.status) : null

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Shariah Screening - {company.ticker}</h1>
          <p className="subtitle">{company.name}</p>
        </div>
        <button className="btn btn-primary" onClick={handleScreen} disabled={running}>
          {running ? 'Screening…' : 'Run screening'}
        </button>
      </div>

      <CompanyTabs ticker={company.ticker} />

      <div className="screening-info">
        <p>
          <strong>Note:</strong> This is a screening tool, not a certification.
          Results are based on financial ratio analysis and should be verified
          with qualified Shariah scholars.
        </p>
      </div>

      {runError && (
        <div className="alert alert-error">
          {runError}{' '}
          <button className="link-btn" onClick={handleScreen}>
            Retry
          </button>
        </div>
      )}
      {resultError && (
        <div className="alert alert-error">
          Couldn't load the screening result.{' '}
          <button className="link-btn" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {!result && !resultError && (
        <div className="empty">
          Not screened yet. Run screening to assess {company.ticker} against the
          versioned methodology.
        </div>
      )}

      {result && badge && (
        <>
          <div className="card">
            <span className={`status-badge ${badge.className}`}>{badge.label}</span>
            <p className="muted">
              Screened {formatAsOf(result.screened_at)} · {result.methodology_name} · methodology v{result.methodology_version}
            </p>
            {result.overall_reason && <p>{result.overall_reason}</p>}
          </div>

          {result.rule_results.length > 0 && (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Rule</th>
                    <th>Verdict</th>
                    <th>Value</th>
                    <th>Threshold</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {result.rule_results.map((rule) => (
                    <tr key={rule.rule_name}>
                      <td>{rule.rule_name}</td>
                      <td>{rule.verdict}</td>
                      <td>{rule.value ?? '—'}</td>
                      <td>{rule.threshold ?? '—'}</td>
                      <td>{rule.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
