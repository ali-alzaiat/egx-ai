import "./Rankings.css";

import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useSignals,
  useScoringModel,
  useUnscorable,
  runSignals,
  startMarketRefresh,
  getSyncStatus,
} from '../api/client'
import { useQueryClient } from '@tanstack/react-query'
import type { SignalTier, SyncJobStatus } from '../types'

const TERMINAL_SYNC: SyncJobStatus['status'][] = ['done', 'partial', 'failed']

// Price refresh runs as a backend job (202 → poll status) — the same flow the
// company page uses. `idle` here means the job vanished (backend restarted).
async function waitForPrices(): Promise<SyncJobStatus> {
  for (;;) {
    await new Promise((resolve) => setTimeout(resolve, 2000))
    const job = await getSyncStatus()
    if (TERMINAL_SYNC.includes(job.status)) return job
    if (job.status === 'idle') throw new Error('Price refresh job was lost — retry')
  }
}

const TIERS: (SignalTier | '')[] = ['', 'STRONGEST', 'STRONG', 'NEUTRAL', 'WEAK', 'WEAKEST']

const FACTOR_LABELS: Record<string, string> = {
  momentum_1m: '1M mom',
  momentum_3m: '3M mom',
  momentum_6m: '6M mom',
  trend_alignment: 'Trend',
  distance_from_high: 'vs 52w high',
  max_drawdown: 'Max DD',
  volatility: 'Volatility',
  liquidity: 'Liquidity',
  volume_confirmation: 'Volume',
}

function tierClass(tier: SignalTier | null): string {
  switch (tier) {
    case 'STRONGEST':
      return 'tier-strongest'
    case 'STRONG':
      return 'tier-strong'
    case 'WEAK':
      return 'tier-weak'
    case 'WEAKEST':
      return 'tier-weakest'
    default:
      return 'tier-neutral'
  }
}

function fmtPct(value: number | undefined): string {
  if (value === undefined || value === null) return '—'
  return `${(value * 100).toFixed(0)}%`
}

// Signed, arrowed and coloured momentum/drawdown/trend cells (F9/F10/F14).
function fmtSigned(value: number | undefined | null): { text: string; className: string } {
  if (value === undefined || value === null) return { text: '—', className: '' }
  const pct = (Math.abs(value) * 100).toFixed(1)
  if (value >= 0) return { text: `▲ +${pct}%`, className: 'positive' }
  return { text: `▼ −${pct}%`, className: 'negative' }
}

export default function Rankings() {
  const queryClient = useQueryClient()
  const [tier, setTier] = useState<SignalTier | ''>('')
  const [minScore, setMinScore] = useState(0)
  const [limit, setLimit] = useState(50)
  const [showUnscorable, setShowUnscorable] = useState(false)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const { data, isLoading, isFetching, error } = useSignals({
    limit,
    tier: tier || undefined,
    min_score: minScore || undefined,
  })
  const { data: model } = useScoringModel()
  const { data: unscorable } = useUnscorable()

  const handleRun = async (): Promise<void> => {
    setRunning(true)
    setRunError(null)
    setToast(null)
    try {
      // Scores were ranking stale bars; pull fresh prices first (409 adopts a
      // live job), wait it out, then score what just landed.
      await startMarketRefresh()
      const job = await waitForPrices()
      if (job.status === 'failed') {
        throw new Error(job.error ?? 'Price refresh failed; scores not re-run')
      }
      const run = await runSignals()
      await queryClient.invalidateQueries({ queryKey: ['signals'] })
      setToast(
        job.status === 'partial'
          ? `Prices partially refreshed — scored as of ${run.as_of}; some tickers failed.`
          : `Fresh prices pulled — scoring complete, results as of ${run.as_of}.`
      )
      window.setTimeout(() => setToast(null), 6000)
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Failed to run the scoring engine')
    } finally {
      setRunning(false)
    }
  }

  const coverage = data?.coverage
  const coveragePct = coverage ? coverage.priced_of_active * 100 : 0

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Market Rankings</h1>
          <p className="subtitle">
            Every company in the EGX universe, scored against the others on the same
            date.
          </p>
        </div>
        <button onClick={handleRun} disabled={running || isFetching} className="btn btn-primary">
          {running ? 'Refreshing prices & scoring…' : 'Re-run scoring'}
        </button>
      </div>

      {toast && (
        <p role="status" className="muted">{toast}</p>
      )}

      {runError && <div className="alert alert-error">{runError}</div>}

      {coverage && (
        <div className="coverage-banner">
          <div className="coverage-main">
            <strong>
              {coverage.analyzable} of {coverage.active_total}
            </strong>{' '}
            listed companies are scorable
            <span className="coverage-pct">({coveragePct.toFixed(1)}% price coverage)</span>
          </div>
          <div className="coverage-detail">
            {coverage.unscorable} excluded: {coverage.unscorable} lack price history from
            the configured source.{' '}
            <button className="link-btn" onClick={() => setShowUnscorable((v) => !v)}>
              {showUnscorable ? 'Hide' : 'Show'} excluded
            </button>
          </div>
          {showUnscorable && unscorable && unscorable.length > 0 && (
            <div className="unscorable-list">
              {unscorable.map((u) => (
                <span key={u.ticker} className="unscorable-chip" title={u.reason ?? ''}>
                  {u.ticker}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {model && (
        <div className="model-note">
          <strong>{model.name} v{model.version}</strong> — {model.description}
        </div>
      )}

      <div className="filters">
        <label>
          Tier
          <select value={tier} onChange={(e) => setTier(e.target.value as SignalTier | '')}>
            {TIERS.map((t) => (
              <option key={t || 'all'} value={t}>
                {t || 'All'}
              </option>
            ))}
          </select>
        </label>
        <label>
          Min score: {minScore}
          <input
            type="range"
            min={0}
            max={95}
            step={5}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
          />
        </label>
        <label>
          Show
          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            {[25, 50, 100, 199].map((n) => (
              <option key={n} value={n}>
                top {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading && !data && <div className="loading">Loading rankings…</div>}
      {error && <div className="alert alert-error">{(error as Error).message}</div>}
      {data?.notice && <div className="alert">{data.notice}</div>}

      {data && data.results.length === 0 && (
        <div className="empty">
          No companies match these filters. Widen the score range or clear the tier.
        </div>
      )}

      {data && data.results.length > 0 && (
        <>
          <div className="table-meta">
            Ranked {data.count} of {data.total} scored · as of {data.as_of} · {data.model}
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Ticker</th>
                <th>Company</th>
                <th>Score</th>
                <th>Tier</th>
                <th>3M mom</th>
                <th>6M mom</th>
                <th>Trend</th>
                <th>Max DD</th>
                <th>Why</th>
              </tr>
            </thead>
          <tbody>
            {data.results.map((s) => {
              const mom3 = fmtSigned(s.factors.momentum_3m)
              const mom6 = fmtSigned(s.factors.momentum_6m)
              const trend = fmtSigned(s.factors.trend_alignment)
              const dd = fmtSigned(s.factors.max_drawdown)
              return (
                <tr key={s.ticker}>
                  <td className="num">{s.rank}</td>
                  <td>
                    <Link to={`/companies/${s.ticker}`} className="ticker-link">
                      {s.ticker}
                    </Link>
                  </td>
                  <td className="name-cell">{s.name ?? '—'}</td>
                  <td className="num score-cell">{s.score?.toFixed(1)}</td>
                  <td>
                    <span className={`tier-badge ${tierClass(s.tier)}`}>{s.tier}</span>
                  </td>
                  <td className={`num ${mom3.className}`}>{mom3.text}</td>
                  <td className={`num ${mom6.className}`}>{mom6.text}</td>
                  <td className={`num ${trend.className}`}>{trend.text}</td>
                  <td className={`num ${dd.className}`}>{dd.text}</td>
                  <td className="why-cell" title={s.rationale ?? ''}>
                    {summarise(s)}
                  </td>
                </tr>
              )
            })}
          </tbody>
          </table>
          <p className="disclaimer">
            {data.disclaimer ??
              'Research signal only, not investment advice. Relative standing within the covered universe.'}
          </p>
        </>
      )}

      {model && (
        <details className="model-factors">
          <summary>How the score is built (v{model.version})</summary>
          <ul>
            {model.factors.map((f) => (
              <li key={f.key}>
                <strong>{f.label}</strong> — weight {(f.weight * 100).toFixed(0)}%,{' '}
                {f.direction === 'HIGHER_IS_BETTER' ? 'higher is better' : 'lower is better'}
              </li>
            ))}
          </ul>
          <p className="muted">
            Each factor is converted to its percentile rank within the covered universe on
            that date, then combined. Percentile columns show where the company sits versus
            the market, not an absolute judgement.
          </p>
        </details>
      )}

    </div>
  )
}

function summarise(signal: {
  percentiles: Record<string, number>
  excluded_factors: string[]
}): string {
  const entries = Object.entries(signal.percentiles).sort((a, b) => b[1] - a[1])
  if (entries.length === 0) return '—'
  const top = entries.slice(0, 2).map(([k, v]) => `${FACTOR_LABELS[k] ?? k} ${fmtPct(v)}`)
  const suffix = signal.excluded_factors.length
    ? ` (${signal.excluded_factors.length} factor(s) missing)`
    : ''
  return top.join(', ') + suffix
}
