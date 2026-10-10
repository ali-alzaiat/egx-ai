import "./Dashboard.css";

import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useCompanies, useDataSources, useSignalCoverage, useSignals } from '../api/client'
import { formatAsOf } from '../lib/format'

function Card({
  label,
  loading,
  error,
  onRetry,
  children,
}: {
  label: string
  loading: boolean
  error: Error | null
  onRetry: () => void
  children: ReactNode
}) {
  return (
    <div className="card">
      <div className="card-label">{label}</div>
      {loading && <div className="card-value">Loading...</div>}
      {!loading && error && (
        <>
          <div className="card-value">—</div>
          <div className="card-subtitle">
            Not available right now.{' '}
            <button className="link-btn" onClick={onRetry}>
              Retry
            </button>
          </div>
        </>
      )}
      {!loading && !error && children}
    </div>
  )
}

export default function Dashboard() {
  const {
    data: companies,
    isLoading: loadingCompanies,
    error: companiesError,
    refetch: refetchCompanies,
  } = useCompanies({ page_size: 1 })
  const {
    data: coverage,
    isLoading: loadingCoverage,
    error: coverageError,
    refetch: refetchCoverage,
  } = useSignalCoverage()
  const {
    data: signals,
    isLoading: loadingSignals,
    error: signalsError,
    refetch: refetchSignals,
  } = useSignals({ limit: 10 })
  const { data: sources } = useDataSources()

  const lastRefresh = (sources ?? [])
    .map((s) => s.last_synced_at)
    .filter((v): v is string => v !== null)
    .sort()
    .pop()

  const coveragePct =
    coverage && coverage.active_total > 0
      ? ((coverage.priced_of_active ?? 0) * 100).toFixed(1)
      : null

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>EGX Stock Analysis & Shariah Screening Platform</p>
        </div>
      </div>

      <div className="card-grid">
        <Card label="Companies tracked" loading={loadingCompanies} error={companiesError} onRetry={() => refetchCompanies()}>
          <div className="card-value">{companies?.total ?? '—'}</div>
          <div className="card-subtitle">EGX-listed companies</div>
        </Card>

        <Card label="Market coverage" loading={loadingCoverage} error={coverageError} onRetry={() => refetchCoverage()}>
          <div className="card-value">{coveragePct !== null ? `${coveragePct}%` : '—'}</div>
          <div className="card-subtitle">active companies with price data</div>
        </Card>

        <Card label="Scored companies" loading={loadingSignals} error={signalsError} onRetry={() => refetchSignals()}>
          <div className="card-value">{signals?.total ?? '—'}</div>
          <div className="card-subtitle">ranked as of {signals?.as_of ? formatAsOf(signals.as_of) : '—'}</div>
        </Card>

        <Card label="Scorable coverage" loading={loadingCoverage} error={coverageError} onRetry={() => refetchCoverage()}>
          <div className="card-value">
            {coverage ? `${coverage.analyzable} of ${coverage.active_total}` : '—'}
          </div>
          <div className="card-subtitle">listed companies are scorable</div>
        </Card>
      </div>

      <p className="muted">
        {lastRefresh ? `Last refresh: ${formatAsOf(lastRefresh)}` : 'Market data has never been refreshed.'}
      </p>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Company</th>
              <th>Score</th>
              <th>Tier</th>
            </tr>
          </thead>
          <tbody>
            {loadingSignals && (
              <tr>
                <td colSpan={4} style={{ textAlign: 'center' }}>
                  Loading scores...
                </td>
              </tr>
            )}
            {!loadingSignals && signalsError && (
              <tr>
                <td colSpan={4}>
                  <div className="alert alert-error">
                    Couldn't load scores.{' '}
                    <button className="link-btn" onClick={() => refetchSignals()}>
                      Retry
                    </button>
                  </div>
                </td>
              </tr>
            )}
            {!loadingSignals && !signalsError && (!signals || signals.results.length === 0) && (
              <tr>
                <td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                  No scores yet.{' '}
                  <Link to="/rankings" className="link-btn">
                    Run scoring from the Rankings page.
                  </Link>
                </td>
              </tr>
            )}
            {signals?.results.map((s) => (
              <tr key={s.ticker}>
                <td>
                  <Link to={`/companies/${s.ticker}`} className="ticker-link">
                    {s.ticker}
                  </Link>
                </td>
                <td>{s.name ?? '—'}</td>
                <td>{s.score?.toFixed(1) ?? '—'}</td>
                <td>{s.tier ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
