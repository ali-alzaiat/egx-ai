import { memo } from 'react'
import type { FairValueResponse } from '../types'
import { formatAsOf, formatPrice } from '../lib/format'
import './FairValueCard.css'

// Weighted fair value always renders paired with its assumptions — never a
// bare point estimate (frontend-catchup-contract Batch A.3).

const LEG_ORDER = ['intrinsic', 'relative', 'fallback'] as const

const LEG_LABEL: Record<string, string> = {
  intrinsic: 'Intrinsic',
  relative: 'Relative',
  fallback: 'Fallback',
}

const VERDICT_LABEL: Record<string, string> = {
  POTENTIALLY_UNDERVALUED: 'Potentially undervalued',
  POTENTIALLY_OVERVALUED: 'Potentially overvalued',
  AROUND_FAIR_VALUE: 'Around fair value',
  INSUFFICIENT_DATA: 'Not enough data',
}

// Rule 10: interpretation only, never a BUY/SELL instruction.
const VERDICT_DETAIL: Record<string, string> = {
  POTENTIALLY_UNDERVALUED:
    'Price is below fair value by more than the required margin for this confidence level; potentially undervalued under these assumptions.',
  POTENTIALLY_OVERVALUED:
    'Price is above fair value by more than the required margin for this confidence level; potentially overvalued under these assumptions.',
  AROUND_FAIR_VALUE:
    'Price is within the required margin of fair value for this confidence level; around fair value under these assumptions.',
  INSUFFICIENT_DATA:
    'No verdict: fair value or current price is unavailable, so no comparison is made.',
}

const VERDICT_BADGE: Record<string, string> = {
  POTENTIALLY_UNDERVALUED: 'healthy',
  POTENTIALLY_OVERVALUED: 'warning',
  AROUND_FAIR_VALUE: 'unknown',
  INSUFFICIENT_DATA: 'unknown',
}

const LADDER_TITLE =
  'Confidence ladder (methodology v1.0): VeryHigh needs a 10% margin, High 15%, Medium 20%, Low/POOR/MISSING 30%. Weaker inputs need a bigger discount before any verdict.'

function statusWord(status: string): string {
  if (status === 'AVAILABLE') return 'Available'
  if (status === 'INVALID') return 'Invalid inputs'
  return 'Not enough data'
}

interface VerdictShape {
  label?: unknown
  detail?: unknown
  discount?: unknown
}

// The API sends verdict as { label, detail, discount }; the frozen
// FairValueResponse type declares a string, so accept both at runtime.
function readVerdict(verdict: unknown): {
  label: string
  detail: string
  discount: string | null
} {
  if (typeof verdict === 'string') {
    return {
      label: verdict,
      detail: VERDICT_DETAIL[verdict] ?? verdict,
      discount: null,
    }
  }
  if (verdict !== null && typeof verdict === 'object') {
    const v = verdict as VerdictShape
    const label =
      typeof v.label === 'string' ? v.label : 'INSUFFICIENT_DATA'
    return {
      label,
      detail:
        typeof v.detail === 'string'
          ? v.detail
          : (VERDICT_DETAIL[label] ?? label),
      discount: typeof v.discount === 'string' ? v.discount : null,
    }
  }
  return {
    label: 'INSUFFICIENT_DATA',
    detail: VERDICT_DETAIL.INSUFFICIENT_DATA ?? 'No verdict available.',
    discount: null,
  }
}

function formatDiscount(discount: string | null): string {
  if (discount === null) return '—'
  const n = Number(discount)
  return Number.isFinite(n) ? `${(n * 100).toFixed(1)}%` : discount
}

function LegRows({ fairValue }: { fairValue: FairValueResponse }) {
  return (
    <>
      {LEG_ORDER.map((leg) => {
        const row = fairValue.legs[leg]
        const available = row.status === 'AVAILABLE'
        return (
          <tr key={leg}>
            <td>
              {LEG_LABEL[leg] ?? leg}{' '}
              <span className="muted">({row.model})</span>
            </td>
            <td>{available ? formatPrice(row.value) : '—'}</td>
            <td>{fairValue.weights[leg] ?? '—'}</td>
            <td>
              <span
                className={`status-badge ${available ? 'healthy' : 'unknown'}`}
              >
                {statusWord(row.status)}
              </span>
            </td>
            <td>{row.reason ?? '—'}</td>
          </tr>
        )
      })}
    </>
  )
}

function FairValueCard({ fairValue }: { fairValue: FairValueResponse }) {
  const verdict = readVerdict(fairValue.verdict)
  const dqStatus = fairValue.confidence.dq_status ?? 'POOR'
  const degraded = dqStatus !== 'OK'
  const fv = fairValue.fair_value
  const available = fv.status === 'AVAILABLE' && fv.value !== null
  const assumptions = Object.entries(fairValue.inputs).filter(
    ([, v]) => v !== null && v !== undefined,
  )
  const bear = fairValue.scenarios.bear.value
  const bull = fairValue.scenarios.bull.value

  return (
    <div className="card fv-card">
      <h2 className="section-title">Weighted fair value</h2>

      <p className="fv-headline">
        {available ? formatPrice(fv.value) : '—'}
        <span className="muted">
          {fairValue.current_price.value
            ? ` (price ${formatPrice(fairValue.current_price.value)})`
            : ' (no current price)'}
        </span>
      </p>

      <p>
        <span
          className={`status-badge ${VERDICT_BADGE[verdict.label] ?? 'unknown'}`}
        >
          {VERDICT_LABEL[verdict.label] ?? verdict.label}
        </span>{' '}
        {verdict.detail}
      </p>

      {verdict.discount !== null ? (
        <p className="muted">
          Implied discount to fair value: {formatDiscount(verdict.discount)}
        </p>
      ) : null}

      {degraded ? (
        <div className="alert alert-error" role="alert">
          Data quality is {dqStatus}: treat this as a wide range, not a point
          estimate. {fairValue.confidence.reason}
          {bear !== null && bull !== null && bear !== undefined && bull !== undefined ? (
            <>
              {' '}
              Range under stated assumptions: bear {formatPrice(bear)} → bull{' '}
              {formatPrice(bull)}.
            </>
          ) : null}
        </div>
      ) : null}

      {!available ? (
        <div className="alert alert-error">
          {fv.reason ?? 'Not enough data for a fair value.'}
        </div>
      ) : null}

      <p className="muted" title={LADDER_TITLE}>
        Confidence {fairValue.confidence.level} · needs a{' '}
        {formatDiscount(fairValue.confidence.required_discount)} margin ·
        financial-statements quality{' '}
        {fairValue.confidence.dq_score === null ||
        fairValue.confidence.dq_score === undefined
          ? 'unscored'
          : `${Number(fairValue.confidence.dq_score).toFixed(1)}/100`}{' '}
        ({dqStatus})
      </p>

      <div className="table-container">
        <table>
          <caption className="muted">
            Per-model legs and the fixed weights behind the headline value
          </caption>
          <thead>
            <tr>
              <th scope="col">Leg</th>
              <th scope="col">Value</th>
              <th scope="col">Weight</th>
              <th scope="col">Status</th>
              <th scope="col">Reason</th>
            </tr>
          </thead>
          <tbody>
            <LegRows fairValue={fairValue} />
          </tbody>
        </table>
      </div>

      <div className="table-container">
        <table>
          <caption className="muted">
            Scenario range under stated assumptions — what each scenario
            implies, not what the price will do
          </caption>
          <thead>
            <tr>
              <th scope="col">Bear</th>
              <th scope="col">Base</th>
              <th scope="col">Bull</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              {(['bear', 'base', 'bull'] as const).map((name) => {
                const s = fairValue.scenarios[name]
                return (
                  <td key={name} title={s.reason ?? undefined}>
                    {s.status === 'AVAILABLE' ? formatPrice(s.value) : '—'}
                  </td>
                )
              })}
            </tr>
          </tbody>
        </table>
        <p className="muted">{fairValue.scenarios.note}</p>
      </div>

      <h3 className="card-label">Key assumptions</h3>
      {assumptions.length > 0 ? (
        <p className="muted">
          {assumptions
            .map(
              ([k, v]) =>
                `${k}=${v} (${fairValue.input_sources[k] ?? 'unknown source'})`,
            )
            .join(' · ')}
        </p>
      ) : (
        <p className="muted">
          No caller-supplied assumptions; legs fell back to metrics or
          INSUFFICIENT_DATA.
        </p>
      )}

      <p className="muted">
        As of {formatAsOf(fairValue.as_of)} · methodology v
        {fairValue.methodology_version} · profile{' '}
        {fairValue.profile.profile_id} (primary:{' '}
        {fairValue.profile.primary_model}, fallback:{' '}
        {fairValue.profile.fallback_model}
        {fairValue.profile.preferred_multiple
          ? `, prefers ${fairValue.profile.preferred_multiple}`
          : ''}
        ) · {fairValue.n_with_data} model legs with data · price as of{' '}
        {formatAsOf(fairValue.current_price.as_of)}
      </p>
    </div>
  )
}

export default memo(FairValueCard)
