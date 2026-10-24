import "./Thesis.css";

import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { assessThesis, updateThesis, useCompanyByTicker, useThesis } from '../api/client'
import { formatAsOf } from '../lib/format'
import CompanyNotFound from '../components/CompanyNotFound'
import type {
  ThesisAssessment,
  ThesisCatalyst,
  ThesisInvalidation,
} from '../types'

// Server-pinned enums (backend/app/thesis/constants.py). Selects are built
// from these so the update form can never submit a value the API rejects.
const INVALIDATION_STATUSES = ['Active', 'Triggered', 'Reassessed'] as const
const LEDGER_CLASSIFICATIONS = ['Confirmed', 'Pending', 'Challenged', 'Invalidated', 'New'] as const
const CATALYST_OUTCOMES = ['Pending', 'Hit', 'Miss', 'Pushed'] as const

const MIN_HORIZON_YEARS = 1
const MAX_HORIZON_YEARS = 30
const DEFAULT_HORIZON_YEARS = 5

function isStale(asOf: string | undefined): boolean {
  if (!asOf) return false
  const t = new Date(asOf).getTime()
  if (Number.isNaN(t)) return false
  return Date.now() - t > 90 * 24 * 60 * 60 * 1000
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  // Never render raw JSON as text — nested detail lives behind title tooltips.
  if (typeof value === 'object') return 'Details'
  return String(value)
}

function formatTitle(value: unknown): string | undefined {
  if (value !== null && typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return undefined
    }
  }
  return undefined
}

function ThesisScoreValue({ score }: { score: ThesisAssessment['score'] }) {
  if (score === null || score === undefined) return <>—</>
  if (typeof score === 'number') return <>{score}</>
  // Backend sends the score payload as an object; surface its scalar leaves.
  const entries = Object.entries(score).filter(
    ([, v]) => v === null || typeof v !== 'object',
  )
  if (entries.length === 0) return <span className="muted">See headline above</span>
  return (
    <span title={formatTitle(score)}>
      {entries.map(([k, v]) => `${k}: ${formatValue(v)}`).join(' · ')}
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  const missing = status === 'INSUFFICIENT_DATA' || status === 'UNKNOWN'
  return (
    <span
      className={missing ? 'thesis-badge thesis-badge-missing' : 'thesis-badge'}
      title={missing ? 'Not enough stored data to determine this' : status}
    >
      {missing ? status : status}
    </span>
  )
}

function KeyValueTable({
  title,
  caption,
  record,
  emptyText,
}: {
  title: string
  caption: string
  record: Record<string, unknown>
  emptyText: string
}) {
  const entries = Object.entries(record ?? {})
  return (
    <div className="card">
      <h2>{title}</h2>
      <p className="muted">{caption}</p>
      {entries.length === 0 ? (
        <p className="muted">{emptyText}</p>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Key</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(([key, value]) => (
                <tr key={key}>
                  <td>{key}</td>
                  <td title={formatTitle(value)}>{formatValue(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function InvalidationRow({ inv }: { inv: ThesisInvalidation }) {
  const triggered = inv.status === 'Triggered'
  return (
    <tr className={triggered ? 'thesis-triggered' : undefined}>
      <td>{inv.metric}</td>
      <td>{inv.threshold}</td>
      <td>{inv.direction}</td>
      <td>{inv.period || '—'}</td>
      <td>{inv.evidence_source || '—'}</td>
      <td>{inv.action || '—'}</td>
      <td><StatusBadge status={inv.status} /></td>
    </tr>
  )
}

function CatalystRow({ catalyst }: { catalyst: ThesisCatalyst }) {
  const window =
    catalyst.window ||
    [catalyst.date_from, catalyst.date_to].filter(Boolean).join(' → ') ||
    '—'
  return (
    <tr>
      <td>{catalyst.event}</td>
      <td>{window}</td>
      <td>{catalyst.variable || '—'}</td>
      <td>{catalyst.expectation || '—'}</td>
      <td><StatusBadge status={catalyst.outcome} /></td>
      <td>{catalyst.label}</td>
    </tr>
  )
}

function ThesisBody({ assessment }: { assessment: ThesisAssessment }) {
  const stale = isStale(assessment.as_of)
  const triggered = assessment.invalidations.filter((inv) => inv.status === 'Triggered')
  const shareholder =
    assessment.header.is_shareholder === null || assessment.header.is_shareholder === undefined
      ? 'Unknown'
      : assessment.header.is_shareholder
        ? 'Yes'
        : 'No'
  // Append-only ledger, oldest first — the order rows were recorded in.
  const ledger = [...assessment.ledger].sort((a, b) =>
    (a.created_at ?? '').localeCompare(b.created_at ?? ''),
  )
  return (
    <>
      {stale ? (
        <div className="alert alert-error" role="alert">
          This thesis is over 90 days old (as of {formatAsOf(assessment.as_of)}).
          Re-assess before relying on it.
        </div>
      ) : null}

      {assessment.needs_reassessment || triggered.length > 0 ? (
        <div className="alert alert-error" role="alert">
          {triggered.length > 0
            ? `Conditions triggered (${triggered.map((inv) => inv.metric).join(', ')}) — `
            : ''}
          this thesis is potentially invalidated under these assumptions. A
          trigger proposes documented reassessment, never an automatic sale:
          confirm by re-assessing above or recording an update below.
        </div>
      ) : null}

      <div className="card">
        <h2>Thesis header</h2>
        <p>
          Fair value:{' '}
          {assessment.header.fair_value.value ?? '—'}{' '}
          <StatusBadge status={assessment.header.fair_value.status} />
        </p>
        <p>Horizon: {assessment.header.horizon_years} years</p>
        <p>Shareholder: {shareholder}</p>
        <p>Score: <ThesisScoreValue score={assessment.score} /></p>
        <p className="muted">
          As of {formatAsOf(assessment.as_of)} · thesis methodology v{assessment.methodology_version} ·
          valuation methodology v{assessment.valuation_methodology_version}
        </p>
      </div>

      <div className="card">
        <h2>Narrative</h2>
        {assessment.narrative ? (
          <p>{assessment.narrative}</p>
        ) : (
          <p className="muted">No narrative stored for this thesis.</p>
        )}
      </div>

      <div className="table-container">
        <table>
          <caption className="muted">
            Labelled assumptions — every number cites its source.
          </caption>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Value</th>
              <th>Horizon</th>
              <th>Source</th>
              <th>Author</th>
            </tr>
          </thead>
          <tbody>
            {assessment.assumptions.length === 0 ? (
              <tr>
                <td colSpan={5} className="muted">No assumptions recorded.</td>
              </tr>
            ) : (
              assessment.assumptions.map((a, i) => (
                <tr key={`${a.metric}-${i}`}>
                  <td>{a.metric}</td>
                  <td>{a.value ?? '—'}</td>
                  <td>{a.horizon ?? '—'}</td>
                  <td>{a.source || '—'}</td>
                  <td>{a.author}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Bulls</h2>
        {assessment.bulls.length === 0 ? (
          <p className="muted">No bull cases recorded.</p>
        ) : (
          <ul>
            {assessment.bulls.map((bull, i) => (
              <li key={i}>{bull}</li>
            ))}
          </ul>
        )}
        <h2>Bears</h2>
        {assessment.bears.length === 0 ? (
          <p className="muted">No bear cases recorded.</p>
        ) : (
          <ul>
            {assessment.bears.map((bear, i) => (
              <li key={i}>{bear}</li>
            ))}
          </ul>
        )}
      </div>

      <KeyValueTable
        title="Scenarios"
        caption="Stored scenario anchors — a range to think with, not a prediction."
        record={assessment.scenarios}
        emptyText="No scenarios stored."
      />
      <KeyValueTable
        title="Sensitivity"
        caption="How the fair value moves when assumptions shift."
        record={assessment.sensitivity}
        emptyText="No sensitivity stored."
      />

      <div className="table-container">
        <table>
          <caption className="muted">
            Stored invalidation conditions. The action on a trigger is always
            documented reassessment — never an automatic sale.
          </caption>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Threshold</th>
              <th>Direction</th>
              <th>Period</th>
              <th>Evidence source</th>
              <th>Action</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {assessment.invalidations.length === 0 ? (
              <tr>
                <td colSpan={7} className="muted">No invalidation conditions stored.</td>
              </tr>
            ) : (
              assessment.invalidations.map((inv) => (
                <InvalidationRow key={`${inv.metric}-v${inv.version}`} inv={inv} />
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="table-container">
        <table>
          <caption className="muted">
            Catalyst records — dated filings confirm them; undated rows stay Tentative.
          </caption>
          <thead>
            <tr>
              <th>Event</th>
              <th>Window</th>
              <th>Variable</th>
              <th>Expectation</th>
              <th>Outcome</th>
              <th>Label</th>
            </tr>
          </thead>
          <tbody>
            {assessment.catalysts.length === 0 ? (
              <tr>
                <td colSpan={6} className="muted">No catalysts recorded.</td>
              </tr>
            ) : (
              assessment.catalysts.map((catalyst) => (
                <CatalystRow key={catalyst.id} catalyst={catalyst} />
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Ledger timeline (oldest first)</h2>
        <p className="muted">
          Append-only record of every documented update — rows are never edited or deleted.
        </p>
        {ledger.length === 0 ? (
          <p className="muted">No ledger entries yet.</p>
        ) : (
          <ol className="thesis-ledger">
            {ledger.map((row, i) => (
              <li key={`${row.created_at}-${i}`}>
                <strong>{row.classification}</strong> · {row.variable} · {row.action}
                <br />
                {row.rationale}
                <br />
                <span className="muted">
                  {row.reviewer || 'No reviewer'} · {formatAsOf(row.created_at)} ·
                  methodology v{row.methodology_version}
                </span>
              </li>
            ))}
          </ol>
        )}
      </div>

      <KeyValueTable
        title="Confidence"
        caption="How much weight to put on this thesis."
        record={assessment.confidence}
        emptyText="No confidence detail stored."
      />
      <KeyValueTable
        title="Data quality"
        caption="Condition of the inputs behind this thesis."
        record={assessment.dq}
        emptyText="No data-quality detail stored."
      />

      <p className="muted">{assessment.disclaimer}</p>
      <p className="muted">
        Thesis methodology v{assessment.methodology_version} · valuation
        methodology v{assessment.valuation_methodology_version} · as of{' '}
        {formatAsOf(assessment.as_of)}
      </p>
    </>
  )
}

function AssessForm({
  companyId,
  onDone,
}: {
  companyId: string
  onDone: () => Promise<void>
}) {
  const [horizon, setHorizon] = useState<string>(String(DEFAULT_HORIZON_YEARS))
  const [shareholder, setShareholder] = useState<string>('unknown')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAssess = async (): Promise<void> => {
    setRunning(true)
    setError(null)
    try {
      const parsed = Number(horizon)
      const horizonYears =
        Number.isFinite(parsed)
          ? Math.min(MAX_HORIZON_YEARS, Math.max(MIN_HORIZON_YEARS, Math.floor(parsed)))
          : DEFAULT_HORIZON_YEARS
      await assessThesis(companyId, {
        horizon_years: horizonYears,
        ...(shareholder === 'unknown' ? {} : { is_shareholder: shareholder === 'yes' }),
      })
      await onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assessment failed')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="card">
      <h2>Assess thesis</h2>
      <p className="muted">
        Valuation inputs left blank resolve server-side from stored data or
        degrade to INSUFFICIENT_DATA — nothing is defaulted.
      </p>
      <fieldset>
        <legend>Assess inputs (all optional)</legend>
        <label>
          Horizon (years, {MIN_HORIZON_YEARS}–{MAX_HORIZON_YEARS})
          <input
            type="number"
            min={MIN_HORIZON_YEARS}
            max={MAX_HORIZON_YEARS}
            step="1"
            value={horizon}
            onChange={(e) => setHorizon(e.target.value)}
            className="filter-input"
          />
        </label>
        <label>
          Shareholder
          <select
            value={shareholder}
            onChange={(e) => setShareholder(e.target.value)}
            className="filter-input"
          >
            <option value="unknown">Unknown</option>
            <option value="yes">Yes — I hold this stock</option>
            <option value="no">No</option>
          </select>
        </label>
      </fieldset>
      {error ? <div className="alert alert-error">{error}</div> : null}
      <button className="btn btn-primary" onClick={handleAssess} disabled={running}>
        {running ? 'Assessing…' : 'Assess thesis'}
      </button>
    </div>
  )
}

function UpdateForm({
  companyId,
  assessment,
  onDone,
}: {
  companyId: string
  assessment: ThesisAssessment
  onDone: () => Promise<void>
}) {
  const [rationale, setRationale] = useState('')
  const [reviewer, setReviewer] = useState('')
  const [classification, setClassification] = useState<string>('Pending')
  const [statuses, setStatuses] = useState<Record<string, string>>({})
  const [outcomes, setOutcomes] = useState<Record<string, string>>({})
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const rationaleBlank = rationale.trim() === ''

  const handleUpdate = async (): Promise<void> => {
    if (rationaleBlank) return
    setRunning(true)
    setError(null)
    try {
      // Only rows the reviewer actually changed travel to the API.
      const invalidations: { metric: string; status: string }[] = []
      for (const inv of assessment.invalidations) {
        const next = statuses[inv.metric]
        if (next !== undefined && next !== inv.status) invalidations.push({ metric: inv.metric, status: next })
      }
      const catalysts: { catalyst_id: string; outcome: string }[] = []
      for (const c of assessment.catalysts) {
        const next = outcomes[c.id]
        if (next !== undefined && next !== c.outcome) catalysts.push({ catalyst_id: c.id, outcome: next })
      }
      await updateThesis(companyId, {
        rationale: rationale.trim(),
        ...(reviewer.trim() === '' ? {} : { reviewer: reviewer.trim() }),
        classification,
        ...(invalidations.length > 0 ? { invalidations } : {}),
        ...(catalysts.length > 0 ? { catalysts } : {}),
      })
      setRationale('')
      setReviewer('')
      setStatuses({})
      setOutcomes({})
      await onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="card">
      <h2>Documented update</h2>
      <p className="muted">
        A rationale is required — status and outcome changes are recorded with
        it in the append-only ledger. Submit stays disabled until you write one.
      </p>
      <fieldset>
        <legend>Update</legend>
        <label>
          Rationale (required)
          <textarea
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            className="filter-input"
            rows={3}
          />
        </label>
        <label>
          Reviewer (optional)
          <input
            type="text"
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            className="filter-input"
          />
        </label>
        <label>
          Classification
          <select
            value={classification}
            onChange={(e) => setClassification(e.target.value)}
            className="filter-input"
          >
            {LEDGER_CLASSIFICATIONS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
      </fieldset>
      {assessment.invalidations.length > 0 ? (
        <fieldset>
          <legend>Invalidation statuses (change only what moved)</legend>
          {assessment.invalidations.map((inv) => (
            <label key={inv.metric}>
              {inv.metric} (now {inv.status})
              <select
                value={statuses[inv.metric] ?? inv.status}
                onChange={(e) =>
                  setStatuses((prev) => ({ ...prev, [inv.metric]: e.target.value }))
                }
                className="filter-input"
              >
                {INVALIDATION_STATUSES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </label>
          ))}
        </fieldset>
      ) : null}
      {assessment.catalysts.length > 0 ? (
        <fieldset>
          <legend>Catalyst outcomes (change only what resolved)</legend>
          {assessment.catalysts.map((c) => (
            <label key={c.id}>
              {c.event} (now {c.outcome})
              <select
                value={outcomes[c.id] ?? c.outcome}
                onChange={(e) =>
                  setOutcomes((prev) => ({ ...prev, [c.id]: e.target.value }))
                }
                className="filter-input"
              >
                {CATALYST_OUTCOMES.map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            </label>
          ))}
        </fieldset>
      ) : null}
      {error ? <div className="alert alert-error">{error}</div> : null}
      <button
        className="btn btn-primary"
        onClick={handleUpdate}
        disabled={running || rationaleBlank}
        title={rationaleBlank ? 'Write a rationale first' : undefined}
      >
        {running ? 'Recording…' : 'Record update'}
      </button>
    </div>
  )
}

export default function Thesis() {
  const { ticker } = useParams<{ ticker: string }>()
  const queryClient = useQueryClient()
  const { data: company, isLoading: companyLoading, error: companyError } = useCompanyByTicker(ticker)
  const {
    data: thesis,
    isLoading: thesisLoading,
    error: thesisError,
    refetch,
  } = useThesis(company?.id)

  const refresh = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ['thesis'] })
    await refetch()
  }

  if (companyLoading || thesisLoading) {
    return <div className="loading">Loading company...</div>
  }

  if (companyError || !company) {
    return <CompanyNotFound ticker={ticker} />
  }

  const assessment = thesis?.assessment ?? null

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Investment Thesis - {company.ticker}</h2>
          <p className="subtitle">{company.name}</p>
        </div>
      </div>


      {thesisError ? (
        <div className="alert alert-error">
          Couldn't load the investment thesis.{' '}
          <button className="link-btn" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      ) : null}

      {!assessment && !thesisError ? (
        <>
          <div className="empty">
            No thesis assessed yet for {company.ticker}. Assessing computes the
            narrative skeleton, scenarios, invalidation conditions, catalyst
            records, and ledger from stored data — nothing is defaulted.
          </div>
          <AssessForm companyId={company.id} onDone={refresh} />
        </>
      ) : null}

      {assessment ? (
        <>
          <ThesisBody assessment={assessment} />
          <AssessForm companyId={company.id} onDone={refresh} />
          <UpdateForm companyId={company.id} assessment={assessment} onDone={refresh} />
        </>
      ) : null}
    </div>
  )
}
