import { useDataQuality } from '../api/client'
import { qualityLabel, qualityTone } from '../lib/quality'
import type { QualityTone } from '../lib/quality'
import type { DataQualityScore } from '../types'

// Canonical scope order — the API returns them in whatever order they were stored.
const SCOPE_ORDER = [
  'price_history',
  'company_profile',
  'financial_statements',
] as const

const SCOPE_LABELS: Record<string, string> = {
  price_history: 'Price history',
  company_profile: 'Company profile',
  financial_statements: 'Financial statements',
}

const BADGE_CLASS: Record<QualityTone, string> = {
  positive: 'healthy',
  warning: 'warning',
  negative: 'error',
  muted: 'unknown',
}

const ICON: Record<QualityTone, string> = {
  positive: '✓',
  warning: '!',
  negative: '✕',
  muted: '–',
}

const TONE_COLOR: Record<QualityTone, string> = {
  positive: 'var(--green)',
  warning: 'var(--yellow)',
  negative: 'var(--red)',
  muted: 'var(--text-secondary)',
}

const BAND_TITLE =
  'Good: 70–100 · Partial: 40–69 · Poor: below 40 · Insufficient data: no data to assess'

const DEFINITION =
  'How much usable data we have for this company, on a 0–100 scale. Higher is better.'

// Bands are the same cut-offs the backend uses; reuse qualityTone so quality.ts
// stays the single status→tone mapping.
function scoreTone(score: number): QualityTone {
  return qualityTone(score >= 70 ? 'OK' : score >= 40 ? 'DEGRADED' : 'POOR')
}

function ScopeSection({ item }: { item: DataQualityScore }) {
  const missing = item.status === 'MISSING'
  const tone = qualityTone(item.status)
  const label = qualityLabel(item.status)
  const pct = (weight: number) => Math.round(weight * 100)

  return (
    <section className="dq-scope">
      <div className="dq-scope-head">
        <span>{SCOPE_LABELS[item.scope] ?? item.scope}</span>
        <span>As of {item.as_of}</span>
      </div>

      <div className="dq-score-row">
        <div className={`dq-score${missing ? ' missing' : ''}`}>
          {missing ? (
            <>
              —<span className="sr-only"> not scored</span>
            </>
          ) : (
            `${item.score.toFixed(1)} / 100`
          )}
        </div>
        <span
          className={`status-badge ${BADGE_CLASS[tone]}`}
          title={BAND_TITLE}
        >
          <span aria-hidden="true">{ICON[tone]}</span> {label}
        </span>
      </div>

      {missing && (
        <p className="dq-score-note">
          Not enough data to score. This is not a judgment on the company.
        </p>
      )}

      {item.components.map((component) => (
        <div className="dq-component" key={component.key}>
          <div className="dq-component-head">
            <span>{component.label}</span>
            <span>weight {pct(component.weight)}%</span>
            {!missing && (
              <span>{Math.round(component.score)} / 100</span>
            )}
          </div>
          {!missing && (
            <div
              className="dq-bar"
              role="progressbar"
              aria-valuenow={component.score}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${component.label}: ${component.score} of 100, weight ${pct(component.weight)}%`}
            >
              <div
                className="dq-bar-fill"
                style={{
                  width: `${component.score}%`,
                  background: TONE_COLOR[scoreTone(component.score)],
                }}
              />
            </div>
          )}
          <p className="dq-component-reason">{component.reason}</p>
        </div>
      ))}

      {/* Issues omitted for MISSING: the strings hard-code "(0/100)", which the
          headline score and component reasons already say in that state. */}
      {item.issues.length > 0 && !missing && (
        <div className="dq-issues">
          <h3 className="card-label">Issues</h3>
          <ul>
            {item.issues.map((issue) => (
              <li className="dq-issue" key={issue}>
                <span aria-hidden="true">!</span> {issue}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

export default function DataQualityCard({ companyId }: { companyId: string }) {
  const { data, isLoading, error } = useDataQuality(companyId)

  const items = data
    ? [...data.items].sort(
        (a, b) =>
          (SCOPE_ORDER as readonly string[]).indexOf(a.scope) -
          (SCOPE_ORDER as readonly string[]).indexOf(b.scope),
      )
    : []

  return (
    <div className="card dq-card">
      <h2 className="section-title">Data quality</h2>
      <p className="dq-definition">{DEFINITION}</p>

      {isLoading && <div className="loading">Loading data quality...</div>}

      {error && (
        <div className="alert alert-error">Couldn't load data quality.</div>
      )}

      {data && items.length === 0 && (
        <>
          <div className="dq-empty">
            <span className="status-badge unknown" aria-hidden="true">
              –
            </span>
            <p>No data-quality assessment has been run for this company yet.</p>
          </div>
          <p className="muted">Refresh market data to compute assessments for every company.</p>
        </>
      )}

      {items.map((item) => (
        <ScopeSection item={item} key={item.scope} />
      ))}

      {data && (
        <footer className="dq-footer">
          <p className="dq-disclaimer">{data.disclaimer}</p>
          <p className="muted">
            {`Bands: 70+ Good · 40–69 Partial · below 40 Poor · Methodology v${data.methodology_version}`}
          </p>
        </footer>
      )}
    </div>
  )
}
