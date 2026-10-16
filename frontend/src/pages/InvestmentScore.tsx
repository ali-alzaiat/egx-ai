import "./InvestmentScore.css";

import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { assessScore, useCompanyByTicker, useScore } from '../api/client'
import { formatAsOf } from '../lib/format'
import CompanyNotFound from '../components/CompanyNotFound'
import CompanyTabs from '../components/CompanyTabs'
import type { ScoreAssessment, ScoreCheck } from '../types'

const COMPONENT_ORDER = ['value', 'past', 'health', 'dividend', 'growth'] as const

const COMPONENT_LABELS: Record<string, string> = {
  value: 'Value',
  past: 'Past performance',
  health: 'Financial health',
  dividend: 'Dividend',
  growth: 'Growth',
}

function isStale(asOf: string | undefined): boolean {
  if (!asOf) return false
  const t = new Date(asOf).getTime()
  if (Number.isNaN(t)) return false
  return Date.now() - t > 90 * 24 * 60 * 60 * 1000
}

function statusWord(status: string): string {
  if (status === 'AVAILABLE' || status === 'PASS') return 'Available'
  if (status === 'FAIL') return 'Fail'
  if (status === 'NOT_RUN') return 'Not run'
  return 'Not enough data'
}

function isInsufficient(status: string): boolean {
  return status !== 'AVAILABLE' && status !== 'PASS' && status !== 'FAIL'
}

function StatusBadge({ status }: { status: string }) {
  const insufficient = isInsufficient(status) && status !== 'NOT_RUN'
  return (
    <span
      className={insufficient ? 'score-badge score-badge-missing' : 'score-badge'}
      title={insufficient ? 'INSUFFICIENT_DATA — not enough stored data to run this' : status}
    >
      {insufficient ? 'INSUFFICIENT_DATA' : statusWord(status)}
    </span>
  )
}

function inputsTitle(check: ScoreCheck): string {
  const entries = Object.entries(check.inputs ?? {})
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => `${k}=${v}`)
  return entries.length > 0 ? entries.join(' · ') : 'No stored inputs'
}

function ScoreBody({ assessment }: { assessment: ScoreAssessment }) {
  const stale = isStale(assessment.as_of)
  const headline = assessment.headline
  const headlineValue = headline.value
  const headlineMissing = headlineValue === null || headlineValue === undefined
  const sources = assessment.inputs_echo?.sources ?? {}
  const sourceList = Object.entries(sources)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => `${k}: ${typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v)}`)
  return (
    <>
      {stale && (
        <div className="alert alert-error" role="alert">
          This score is over 90 days old (as of {formatAsOf(assessment.as_of)}).
          Re-assess before relying on it.
        </div>
      )}

      <div className="card">
        <h2>Headline score</h2>
        <p className="headline-value">
          {headlineMissing ? '—' : headlineValue.toFixed(1)}
          <span className="muted"> / 100</span>{' '}
          {headlineMissing && <StatusBadge status={headline.status} />}
        </p>
        <p>{headline.detail}</p>
        <p className="muted">{headline.reason}</p>
        <p className="muted">
          As of {formatAsOf(assessment.as_of)} · methodology v{assessment.methodology_version} ·
          valuation v{assessment.valuation_methodology_version} · profile {assessment.profile.profile_id} ({assessment.profile.health_track})
        </p>
      </div>

      <div className="card">
        <h2>Confidence — {assessment.confidence.level}</h2>
        <p>{assessment.confidence.reason}</p>
        <p className="muted">
          {assessment.n_with_data} of {assessment.n_checks_total} checks with data
          {assessment.confidence.dq_score !== null && assessment.confidence.dq_score !== undefined
            ? ` · data-quality score ${assessment.confidence.dq_score}`
            : ''}
          {` · ${assessment.confidence.n_checks_run} checks run`}
        </p>
      </div>

      <div className="table-container">
        <table>
          <caption className="muted">
            Five components, equal-weighted; the headline is their mean and stays
            blank below the data floor — never a default score.
          </caption>
          <thead>
            <tr>
              <th>Component</th>
              <th>Score</th>
              <th>Status</th>
              <th>Checks passed</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {COMPONENT_ORDER.map((key) => {
              const c = assessment.components[key]
              if (!c) return null
              return (
                <tr key={key}>
                  <td>{COMPONENT_LABELS[key] ?? key}</td>
                  <td>{c.score === null || c.score === undefined ? '—' : c.score.toFixed(1)}</td>
                  <td><StatusBadge status={c.status} /></td>
                  <td>{c.passes}/{c.total}</td>
                  <td>{c.reason || '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {assessment.checks.length > 0 && (
        <div className="table-container">
          <table>
            <caption className="muted">
              Per-check detail — hover a check for the stored inputs behind it.
            </caption>
            <thead>
              <tr>
                <th>Check</th>
                <th>Component</th>
                <th>Status</th>
                <th>Threshold</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {assessment.checks.map((check) => (
                <tr key={`${check.component}:${check.check_key}`} title={inputsTitle(check)}>
                  <td>{check.check_key}</td>
                  <td>{COMPONENT_LABELS[check.component] ?? check.component}</td>
                  <td><StatusBadge status={check.status} /></td>
                  <td>{check.threshold || '—'}</td>
                  <td>{check.reason || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {assessment.checks_not_run.length > 0 && (
        <div className="card">
          <h2>Checks not run ({assessment.checks_not_run.length})</h2>
          <p className="muted">{assessment.checks_not_run.join(', ')}</p>
        </div>
      )}

      <div className="card">
        <h2>Buy zone (display only)</h2>
        <p>
          {typeof assessment.buy_zone.in_buy_zone === 'boolean'
            ? assessment.buy_zone.in_buy_zone
              ? 'Price is within the margin-of-safety zone — potentially of interest under these assumptions.'
              : 'Price is above the margin-of-safety zone under these assumptions.'
            : String(assessment.buy_zone.reason ?? 'Buy zone not computed.')}
        </p>
        <p className="muted">This is context, not advice.</p>
      </div>

      <p className="muted">{assessment.disclaimer}</p>
      <p className="muted" title={sourceList.join('\n') || 'No recorded sources'}>
        Scale {assessment.scale} · score methodology v{assessment.methodology_version} ·
        valuation methodology v{assessment.valuation_methodology_version}
        {sourceList.length > 0 ? ` · sources: ${sourceList.join(' · ')}` : ''}
      </p>
    </>
  )
}

export default function InvestmentScore() {
  const { ticker } = useParams<{ ticker: string }>()
  const queryClient = useQueryClient()
  const { data: company, isLoading: companyLoading, error: companyError } = useCompanyByTicker(ticker)
  const {
    data: score,
    isLoading: scoreLoading,
    error: scoreError,
    refetch,
  } = useScore(company?.id)

  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  const handleAssess = async (): Promise<void> => {
    if (!company) return
    setRunning(true)
    setRunError(null)
    try {
      await assessScore(company.id)
      await queryClient.invalidateQueries({ queryKey: ['score'] })
      await refetch()
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Assessment failed')
    } finally {
      setRunning(false)
    }
  }

  if (companyLoading || scoreLoading) {
    return <div className="loading">Loading company...</div>
  }

  if (companyError || !company) {
    return <CompanyNotFound ticker={ticker} />
  }

  const assessment = score?.assessment ?? null

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Investment Score - {company.ticker}</h1>
          <p className="subtitle">{company.name}</p>
        </div>
        <button className="btn btn-primary" onClick={handleAssess} disabled={running}>
          {running ? 'Assessing…' : 'Assess score'}
        </button>
      </div>

      <CompanyTabs ticker={company.ticker} />

      {runError && (
        <div className="alert alert-error">
          {runError}{' '}
          <button className="link-btn" onClick={handleAssess}>
            Retry
          </button>
        </div>
      )}
      {scoreError && (
        <div className="alert alert-error">
          Couldn't load the investment score.{' '}
          <button className="link-btn" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {!assessment && !scoreError && (
        <div className="empty">
          No score assessed yet for {company.ticker}. Assess to compute the
          five-component score from stored data — nothing is defaulted.
        </div>
      )}

      {assessment && <ScoreBody assessment={assessment} />}
    </div>
  )
}
