import "./ShariahScreening.css";

import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  estimatePurification,
  recordEgxMembership,
  screenCompany,
  useCompanyByTicker,
  useEgxMembership,
  usePurification,
  useScreeningResult,
} from '../api/client'
import { formatAsOf } from '../lib/format'
import CompanyNotFound from '../components/CompanyNotFound'
import CompanyTabs from '../components/CompanyTabs'

// ─── Local shapes (shared types/index.ts is router-owned; do not extend it) ───
// Backend GET …/companies/{id} also returns report_date/report_date_reason/
// data_quality, which the frozen ScreeningResult type does not declare.
interface ScreeningResultExt {
  report_date?: string | null
  report_date_reason?: string | null
}

// Backend GET …/egx-membership returns a side-by-side envelope, while POST
// returns the flat record the frozen EgxMembership type declares. Accept both.
interface EgxSideRecord {
  member: boolean
  review_cycle: string
  effective_date: string | null
  source: string | null
  note: string | null
}

interface EgxSideBySide {
  our_verdict: {
    is_compliant: boolean | null
    status: string
    methodology_version: string
    screened_at: string
    report_date: string | null
  } | null
  egx33: EgxSideRecord | null
  history: EgxSideRecord[]
  discrepancy: { flagged: boolean; note: string | null }
}

type EgxView =
  | { kind: 'side-by-side'; view: EgxSideBySide }
  | { kind: 'flat'; record: EgxSideRecord }

function toEgxView(raw: unknown): EgxView | null {
  if (typeof raw !== 'object' || raw === null) return null
  if ('egx33' in raw || 'our_verdict' in raw) {
    return { kind: 'side-by-side', view: raw as EgxSideBySide }
  }
  if ('member' in raw && 'review_cycle' in raw) {
    return { kind: 'flat', record: raw as EgxSideRecord }
  }
  return null
}

function verdictBadge(status: string): { label: string; className: string } {
  if (status === 'COMPLIANT') return { label: 'Compliant', className: 'healthy' }
  if (status === 'NON_COMPLIANT') return { label: 'Not compliant', className: 'error' }
  return { label: 'Not enough data', className: 'unknown' }
}

// Rule verdicts are PASS / FAIL / INSUFFICIENT_DATA (backend ScreeningVerdict).
// INSUFFICIENT_DATA is the "unknown" state: badge stays visible, reason explains.
function ruleBadge(verdict: string): { label: string; className: string } {
  if (verdict === 'PASS') return { label: 'Pass', className: 'healthy' }
  if (verdict === 'FAIL') return { label: 'Fail', className: 'error' }
  return { label: 'Unknown — insufficient data', className: 'unknown' }
}

function purificationBadge(status: string): { label: string; className: string } {
  if (status === 'OK') return { label: 'Estimate', className: 'healthy' }
  return { label: 'Insufficient data', className: 'unknown' }
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
  const {
    data: purification,
    isLoading: purificationLoading,
    refetch: refetchPurification,
  } = usePurification(company?.id)
  const {
    data: membership,
    isLoading: membershipLoading,
    refetch: refetchMembership,
  } = useEgxMembership(company?.id)

  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [purInputs, setPurInputs] = useState<Record<string, string>>({})
  const [purRunning, setPurRunning] = useState(false)
  const [purError, setPurError] = useState<string | null>(null)
  const [egxInputs, setEgxInputs] = useState({ member: true, review_cycle: '', effective_date: '', source: '', note: '' })
  const [egxRunning, setEgxRunning] = useState(false)
  const [egxError, setEgxError] = useState<string | null>(null)

  const handleScreen = async (): Promise<void> => {
    if (!company) return
    setRunning(true)
    setRunError(null)
    try {
      await screenCompany(company.id)
      await queryClient.invalidateQueries({ queryKey: ['screening'] })
      await queryClient.invalidateQueries({ queryKey: ['egxMembership'] })
      await refetch()
      await refetchMembership()
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Screening failed')
    } finally {
      setRunning(false)
    }
  }

  const setPurInput = (key: string, value: string): void => {
    setPurInputs((prev) => ({ ...prev, [key]: value }))
  }

  const numOrUndefined = (raw: string | undefined): number | undefined => {
    if (raw === undefined || raw.trim() === '') return undefined
    const n = Number(raw)
    return Number.isFinite(n) ? n : undefined
  }

  const handlePurify = async (): Promise<void> => {
    if (!company) return
    setPurRunning(true)
    setPurError(null)
    try {
      await estimatePurification(company.id, {
        dividend_egp: numOrUndefined(purInputs.dividend_egp),
        dps: numOrUndefined(purInputs.dps),
        shares_held: numOrUndefined(purInputs.shares_held),
        non_permissible_revenue: numOrUndefined(purInputs.non_permissible_revenue),
        total_revenue: numOrUndefined(purInputs.total_revenue),
        ratio_provenance: purInputs.ratio_provenance?.trim() || undefined,
        dps_source: purInputs.dps_source?.trim() || undefined,
        dps_date: purInputs.dps_date?.trim() || undefined,
      })
      await queryClient.invalidateQueries({ queryKey: ['purification'] })
      await refetchPurification()
    } catch (err) {
      setPurError(err instanceof Error ? err.message : 'Purification failed')
    } finally {
      setPurRunning(false)
    }
  }

  const handleEgxRecord = async (): Promise<void> => {
    if (!company) return
    setEgxRunning(true)
    setEgxError(null)
    try {
      await recordEgxMembership(company.id, {
        member: egxInputs.member,
        review_cycle: egxInputs.review_cycle.trim(),
        effective_date: egxInputs.effective_date.trim() || undefined,
        source: egxInputs.source.trim(),
        note: egxInputs.note.trim() || undefined,
      })
      await queryClient.invalidateQueries({ queryKey: ['egxMembership'] })
      await refetchMembership()
    } catch (err) {
      setEgxError(err instanceof Error ? err.message : 'Recording failed')
    } finally {
      setEgxRunning(false)
    }
  }

  if (companyLoading || resultLoading) {
    return <div className="loading">Loading company...</div>
  }

  if (companyError || !company) {
    return <CompanyNotFound ticker={ticker} />
  }

  const badge = result ? verdictBadge(result.status) : null
  const resultExt = result as unknown as ScreeningResultExt | null
  const purBadge = purification ? purificationBadge(purification.status) : null
  const egxView = toEgxView(membership)

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
          with qualified Shariah scholars. Nothing here is a recommendation to
          buy or sell.
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
            {resultExt?.report_date ? (
              <p className="muted">
                Report period ending {formatAsOf(resultExt.report_date)}
                {resultExt.report_date_reason ? ` — ${resultExt.report_date_reason}` : ''}
              </p>
            ) : null}
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
                    <th>Missing input</th>
                    <th>Source</th>
                    <th>Source date</th>
                  </tr>
                </thead>
                <tbody>
                  {result.rule_results.map((rule) => {
                    const rb = ruleBadge(rule.verdict)
                    return (
                      <tr key={rule.rule_name}>
                        <td>{rule.rule_name}</td>
                        <td>
                          <span className={`status-badge ${rb.className}`} title={rule.reason}>
                            {rb.label}
                          </span>
                        </td>
                        <td>{rule.value ?? '—'}</td>
                        <td>{rule.threshold ?? '—'}</td>
                        <td>{rule.reason}</td>
                        <td>{rule.missing_input ?? '—'}</td>
                        <td>{rule.source ?? '—'}</td>
                        <td>{rule.source_date ? formatAsOf(rule.source_date) : '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <div className="card">
        <h2>Purification estimate (EGP)</h2>
        <p className="muted">
          Dividend-method estimate. The amount stays empty until a ratio exists —
          provide non-permissible and total revenue with provenance, or accept an
          honest INSUFFICIENT_DATA outcome.
        </p>
        <p className="formula" title="Zoya dividend method = Islamicly ratio = MSCI complement">
          purify_EGP = dividend_EGP_received × (non_permissible_revenue / total_revenue)
        </p>
        {purificationLoading && <p className="muted">Loading estimate…</p>}
        {!purificationLoading && !purification && (
          <p className="muted">No purification estimate recorded yet.</p>
        )}
        {purification && purBadge && (
          <>
            <p>
              <span className={`status-badge ${purBadge.className}`}>{purBadge.label}</span>{' '}
              <strong>Amount to purify:</strong>{' '}
              {purification.amount_egp ?? '—'}{' '}
              {purification.amount_egp ? 'EGP' : ''}
              <span className="muted"> · {purification.branch}</span>
            </p>
            <p className="muted">
              Doctrine: {purification.doctrine} · Ratio: {purification.ratio ?? '—'}
              {purification.ratio_provenance ? ` (${purification.ratio_provenance})` : ''} ·
              DPS: {purification.dps ?? '—'}
              {purification.dividend_egp ? ` · Dividend received: ${purification.dividend_egp} EGP` : ''}
              {purification.reason ? ` · ${purification.reason}` : ''}
              {purification.missing_input ? ` · Missing: ${purification.missing_input}` : ''}
            </p>
            {purification.note ? (
              <p className="muted">{purification.note}</p>
            ) : null}
          </>
        )}
        <div className="form-grid">
          <label>
            Dividend (EGP)
            <input type="number" step="any" value={purInputs.dividend_egp ?? ''} onChange={(e) => setPurInput('dividend_egp', e.target.value)} />
          </label>
          <label>
            DPS
            <input type="number" step="any" value={purInputs.dps ?? ''} onChange={(e) => setPurInput('dps', e.target.value)} />
          </label>
          <label>
            Shares held
            <input type="number" step="any" value={purInputs.shares_held ?? ''} onChange={(e) => setPurInput('shares_held', e.target.value)} />
          </label>
          <label>
            Non-permissible revenue
            <input type="number" step="any" value={purInputs.non_permissible_revenue ?? ''} onChange={(e) => setPurInput('non_permissible_revenue', e.target.value)} />
          </label>
          <label>
            Total revenue
            <input type="number" step="any" value={purInputs.total_revenue ?? ''} onChange={(e) => setPurInput('total_revenue', e.target.value)} />
          </label>
          <label>
            Ratio provenance
            <input value={purInputs.ratio_provenance ?? ''} onChange={(e) => setPurInput('ratio_provenance', e.target.value)} placeholder="e.g. 2024 annual report p. 12" />
          </label>
          <label>
            DPS source
            <input value={purInputs.dps_source ?? ''} onChange={(e) => setPurInput('dps_source', e.target.value)} />
          </label>
          <label>
            DPS date (YYYY-MM-DD)
            <input value={purInputs.dps_date ?? ''} onChange={(e) => setPurInput('dps_date', e.target.value)} placeholder="2025-03-15" />
          </label>
        </div>
        {purError && <div className="alert alert-error">{purError}</div>}
        <button className="btn btn-secondary" onClick={handlePurify} disabled={purRunning}>
          {purRunning ? 'Estimating…' : 'Estimate purification'}
        </button>
      </div>

      <div className="card">
        <h2>EGX33 membership</h2>
        <p className="muted">
          Dated catalyst record (Feb/Aug review cycle). Shown side-by-side with
          our verdict — membership never overrides the screening result.
        </p>
        {membershipLoading && <p className="muted">Loading membership…</p>}
        {!membershipLoading && !egxView && (
          <p className="muted">No EGX33 membership recorded for {company.ticker}.</p>
        )}
        {egxView?.kind === 'flat' && (
          <p>
            <strong>{egxView.record.member ? 'Member' : 'Not a member'}</strong>
            {' '}· {egxView.record.review_cycle}
            {egxView.record.effective_date ? ` · effective ${formatAsOf(egxView.record.effective_date)}` : ''}
            {egxView.record.source ? ` · source: ${egxView.record.source}` : ''}
            {egxView.record.note ? ` · ${egxView.record.note}` : ''}
          </p>
        )}
        {egxView?.kind === 'side-by-side' && (
          <>
            <div className="egx-grid">
              <div className="egx-col">
                <h3>Our screening verdict</h3>
                {egxView.view.our_verdict ? (
                  <p>
                    <span className={`status-badge ${verdictBadge(egxView.view.our_verdict.status).className}`}>
                      {verdictBadge(egxView.view.our_verdict.status).label}
                    </span>
                    <span className="muted">
                      {' '}· methodology v{egxView.view.our_verdict.methodology_version}
                      {' '}· screened {formatAsOf(egxView.view.our_verdict.screened_at)}
                    </span>
                  </p>
                ) : (
                  <p className="muted">Not screened yet — run screening above.</p>
                )}
              </div>
              <div className="egx-col">
                <h3>EGX33 membership</h3>
                {egxView.view.egx33 ? (
                  <p>
                    <strong>{egxView.view.egx33.member ? 'Member' : 'Not a member'}</strong>
                    {' '}· {egxView.view.egx33.review_cycle}
                    {egxView.view.egx33.effective_date ? ` · effective ${formatAsOf(egxView.view.egx33.effective_date)}` : ''}
                    {egxView.view.egx33.source ? ` · source: ${egxView.view.egx33.source}` : ''}
                    {egxView.view.egx33.note ? ` · ${egxView.view.egx33.note}` : ''}
                  </p>
                ) : (
                  <p className="muted">No EGX33 membership recorded for {company.ticker}.</p>
                )}
              </div>
            </div>
            {egxView.view.discrepancy.flagged && egxView.view.discrepancy.note ? (
              <div className="alert alert-warning">{egxView.view.discrepancy.note}</div>
            ) : null}
            {egxView.view.history.length > 1 && (
              <ul className="history-list">
                {egxView.view.history.map((h) => (
                  <li key={h.review_cycle}>
                    {h.review_cycle}: {h.member ? 'member' : 'not a member'}
                    {h.source ? ` — ${h.source}` : ''}
                  </li>
                ))}
              </ul>
            )}
            <p className="muted">
              Reconciliation is informational only: an EGX33 listing never turns a
              failed screen into a pass, and our verdict never edits the EGX record.
            </p>
          </>
        )}
        <div className="form-grid">
          <label>
            Member
            <input type="checkbox" checked={egxInputs.member} onChange={(e) => setEgxInputs({ ...egxInputs, member: e.target.checked })} />
          </label>
          <label>
            Review cycle
            <input value={egxInputs.review_cycle} onChange={(e) => setEgxInputs({ ...egxInputs, review_cycle: e.target.value })} placeholder="2026-02 or 2026-08" />
          </label>
          <label>
            Effective date
            <input value={egxInputs.effective_date} onChange={(e) => setEgxInputs({ ...egxInputs, effective_date: e.target.value })} placeholder="2026-02-01" />
          </label>
          <label>
            Source
            <input value={egxInputs.source} onChange={(e) => setEgxInputs({ ...egxInputs, source: e.target.value })} placeholder="e.g. EGX bulletin" />
          </label>
          <label>
            Note
            <input value={egxInputs.note} onChange={(e) => setEgxInputs({ ...egxInputs, note: e.target.value })} />
          </label>
        </div>
        {egxError && <div className="alert alert-error">{egxError}</div>}
        <button className="btn btn-secondary" onClick={handleEgxRecord} disabled={egxRunning}>
          {egxRunning ? 'Recording…' : 'Record membership'}
        </button>
      </div>
    </div>
  )
}
