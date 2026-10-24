import "./Disclosures.css";

import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  parseFiling,
  registerFiling,
  uploadFiling,
  useCompanyByTicker,
  useComparison,
  useDiffs,
  useFacts,
  useFilings,
} from '../api/client'
import { formatAsOf } from '../lib/format'
import CompanyNotFound from '../components/CompanyNotFound'
import type { DisclosureDiff, DisclosureFact, DisclosureFiling } from '../types'

// Company-scoped analyst surface for Phase 7 disclosures. Mounted by the
// router at /companies/:ticker/disclosures (no CompanyTabs entry — linked
// from the Financial Data page header). Mirrors don't crawl: register/upload
// only point at analyst-supplied sources, and missing values stay UNKNOWN,
// never zero.

const METRIC_PRESETS = ['revenue', 'net_income', 'total_assets', 'total_equity', 'eps'] as const

function renderPrimitive(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  // Never render raw JSON as text — nested detail lives behind title tooltips.
  return 'Details'
}

function summaryOf(record: Record<string, unknown>, keys: string[]): string {
  const parts: string[] = []
  for (const key of keys) {
    const value = record[key]
    if (value !== null && value !== undefined && value !== '') {
      parts.push(`${key}=${renderPrimitive(value)}`)
    }
  }
  return parts.join(' · ')
}

function recordTitle(record: Record<string, unknown>): string {
  try {
    return JSON.stringify(record, null, 2)
  } catch {
    return 'No detail recorded'
  }
}

// Generic key/value renderer for the comparison + margin payloads, whose
// exact keys vary by metric (comparison is Record<string, unknown>).
function asRecord(value: unknown): Record<string, unknown> | null {
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  // Some payloads arrive double-encoded (a JSON string instead of an object).
  if (typeof value === 'string' && value.trim().startsWith('{')) {
    try {
      const parsed: unknown = JSON.parse(value)
      if (parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
    } catch {
      return null
    }
  }
  return null
}

function RenderRecord({ record }: { record: Record<string, unknown> }) {
  const entries = Object.entries(record ?? {})
  if (entries.length === 0) return <span className="muted">No detail returned.</span>
  return (
    <dl className="disclosure-record">
      {entries.map(([key, value]) => {
        const nested = asRecord(value)
        return (
          <div key={key} className="disclosure-record-row">
            <dt>{key}</dt>
            <dd title={nested ? recordTitle({ [key]: nested }) : undefined}>
              {nested ? (
                <RenderRecord record={nested} />
              ) : Array.isArray(value) ? (
                value.map((item) => renderPrimitive(item)).join(', ') || '—'
              ) : (
                renderPrimitive(value)
              )}
            </dd>
          </div>
        )
      })}
    </dl>
  )
}

function StatusBadge({ status }: { status: string }) {
  const unknown = status === 'UNKNOWN'
  return (
    <span
      className={unknown ? 'disclosure-badge disclosure-badge-missing' : 'disclosure-badge'}
      title={unknown ? 'UNKNOWN — value missing, never defaulted to zero' : status}
    >
      {unknown ? 'UNKNOWN' : status || '—'}
    </span>
  )
}

function FilingRow({
  filing,
  parsing,
  onParse,
}: {
  filing: DisclosureFiling
  parsing: boolean
  onParse: (filing: DisclosureFiling) => void
}) {
  return (
    <tr>
      <td>
        <a href={filing.filing_url} target="_blank" rel="noreferrer">
          {filing.filing_url.length > 48 ? `${filing.filing_url.slice(0, 48)}…` : filing.filing_url}
        </a>
        <div className="muted">{filing.bulletin_id ?? 'no bulletin id'}</div>
      </td>
      <td>{formatAsOf(filing.report_date)}</td>
      <td>{filing.filing_type || '—'}</td>
      <td>{filing.accounting_basis || '—'}</td>
      <td>{filing.has_bytes ? 'Stored' : 'Reference only'}</td>
      <td>{formatAsOf(filing.downloaded_at)}</td>
      <td>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={parsing}
          onClick={() => onParse(filing)}
        >
          {parsing ? 'Parsing…' : 'Parse'}
        </button>
      </td>
    </tr>
  )
}

function FactRow({ fact }: { fact: DisclosureFact }) {
  const rawValue = fact.value?.value
  const periodBits = [
    fact.period?.end ? formatAsOf(fact.period.end) : null,
    fact.period?.type,
    fact.period?.audit_state,
  ].filter((bit) => bit !== null && bit !== undefined && bit !== '')
  const locatorText = summaryOf(fact.locator ?? {}, ['page', 'table_id', 'table', 'row', 'col', 'bbox', 'cell'])
  const extractionText = summaryOf(fact.extraction ?? {}, ['engine', 'method', 'accuracy', 'confidence'])
  const provenanceText = [locatorText, extractionText].filter((s) => s !== '').join(' · ')
  return (
    <tr id={`fact-${fact.id}`}>
      <td>{fact.metric}</td>
      <td>
        {rawValue ?? '—'} {fact.currency_unit ? <span className="muted">{fact.currency_unit}</span> : null}{' '}
        <StatusBadge status={fact.status} />
      </td>
      <td>{periodBits.length > 0 ? periodBits.join(' · ') : '—'}</td>
      <td>
        {fact.source?.filing_url ? (
          <a href={fact.source.filing_url} target="_blank" rel="noreferrer">
            Filing link
          </a>
        ) : (
          '—'
        )}
        <div className="muted">
          {[fact.source?.bulletin_id, fact.source?.report_date ? formatAsOf(fact.source.report_date) : null, fact.source?.filing_type]
            .filter((bit) => bit !== null && bit !== undefined && bit !== '')
            .join(' · ') || 'no filing detail'}
        </div>
        {fact.accounting_basis ? <div className="muted">Basis: {fact.accounting_basis}</div> : null}
      </td>
      <td title={recordTitle({ locator: fact.locator ?? {}, extraction: fact.extraction ?? {} })}>
        {provenanceText || '—'}
      </td>
      <td>{fact.eas_tags && fact.eas_tags.length > 0 ? fact.eas_tags.join(', ') : '—'}</td>
      <td>
        {fact.is_restated ? <span className="disclosure-flag">Restated</span> : <span className="muted">—</span>}
        {fact.supersedes ? (
          <div>
            <a href={`#fact-${fact.supersedes}`}>Supersedes prior fact</a>
          </div>
        ) : null}
      </td>
    </tr>
  )
}

function DiffRow({ diff }: { diff: DisclosureDiff }) {
  return (
    <tr>
      <td>{diff.metric}</td>
      <td>{diff.kind ?? '—'}</td>
      <td>{diff.prior_period ? formatAsOf(diff.prior_period) : '—'}</td>
      <td>{diff.current_period ? formatAsOf(diff.current_period) : '—'}</td>
      <td>
        {diff.prior_value ?? '—'} → {diff.current_value ?? '—'}
      </td>
      <td>
        {diff.delta ?? '—'}
        {diff.delta_pct ? <span className="muted"> ({diff.delta_pct})</span> : null}
      </td>
    </tr>
  )
}

export default function Disclosures() {
  const { ticker } = useParams<{ ticker: string }>()
  const queryClient = useQueryClient()
  const { data: company, isLoading: companyLoading, error: companyError } = useCompanyByTicker(ticker)
  const {
    data: filings,
    isLoading: filingsLoading,
    error: filingsError,
    refetch: refetchFilings,
  } = useFilings(company?.id)
  const {
    data: facts,
    isLoading: factsLoading,
    error: factsError,
    refetch: refetchFacts,
  } = useFacts(company?.id)

  const [metricDraft, setMetricDraft] = useState<string>('revenue')
  const [metric, setMetric] = useState<string>('revenue')
  const {
    data: comparison,
    isLoading: comparisonLoading,
    error: comparisonError,
    refetch: refetchComparison,
  } = useComparison(company?.id, metric)
  const {
    data: diffs,
    isLoading: diffsLoading,
    error: diffsError,
    refetch: refetchDiffs,
  } = useDiffs(company?.id)

  const [regUrl, setRegUrl] = useState('')
  const [regBulletin, setRegBulletin] = useState('')
  const [regDate, setRegDate] = useState('')
  const [regType, setRegType] = useState('')
  const [regBasis, setRegBasis] = useState('')
  const [regHash, setRegHash] = useState('')
  const [registerBusy, setRegisterBusy] = useState(false)
  const [registerError, setRegisterError] = useState<string | null>(null)
  const [registerOk, setRegisterOk] = useState<string | null>(null)

  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadDate, setUploadDate] = useState('')
  const [uploadType, setUploadType] = useState('')
  const [uploadBasis, setUploadBasis] = useState('')
  const [uploadBulletin, setUploadBulletin] = useState('')
  const [uploadBusy, setUploadBusy] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadOk, setUploadOk] = useState<string | null>(null)

  const [parsingId, setParsingId] = useState<string | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const [parseOk, setParseOk] = useState<string | null>(null)

  const refreshDisclosures = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ['filings'] })
    await queryClient.invalidateQueries({ queryKey: ['facts'] })
    await queryClient.invalidateQueries({ queryKey: ['comparison'] })
    await queryClient.invalidateQueries({ queryKey: ['diffs'] })
    await refetchFilings()
    await refetchFacts()
    await refetchComparison()
    await refetchDiffs()
  }

  const handleRegister = async (): Promise<void> => {
    if (!company) return
    setRegisterBusy(true)
    setRegisterError(null)
    setRegisterOk(null)
    try {
      const res = await registerFiling({
        company_id: company.id,
        filing_url: regUrl.trim(),
        report_date: regDate,
        ...(regBulletin.trim() !== '' ? { bulletin_id: regBulletin.trim() } : {}),
        ...(regType.trim() !== '' ? { filing_type: regType.trim() } : {}),
        ...(regBasis.trim() !== '' ? { accounting_basis: regBasis.trim() } : {}),
        ...(regHash.trim() !== '' ? { content_hash: regHash.trim() } : {}),
      })
      await refreshDisclosures()
      setRegisterOk(res.created ? 'Filing registered.' : 'Filing already registered — reference kept.')
    } catch (err) {
      setRegisterError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setRegisterBusy(false)
    }
  }

  const handleUpload = async (): Promise<void> => {
    if (!company || !uploadFile) return
    setUploadBusy(true)
    setUploadError(null)
    setUploadOk(null)
    try {
      const form = new FormData()
      form.set('company_id', company.id)
      form.set('file', uploadFile)
      form.set('report_date', uploadDate)
      if (uploadBulletin.trim() !== '') form.set('bulletin_id', uploadBulletin.trim())
      if (uploadType.trim() !== '') form.set('filing_type', uploadType.trim())
      if (uploadBasis.trim() !== '') form.set('accounting_basis', uploadBasis.trim())
      const res = await uploadFiling(form)
      await refreshDisclosures()
      setUploadOk(res.created ? 'Filing uploaded.' : 'Filing already stored — reference kept.')
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploadBusy(false)
    }
  }

  const handleParse = async (filing: DisclosureFiling): Promise<void> => {
    setParsingId(filing.id)
    setParseError(null)
    setParseOk(null)
    try {
      await parseFiling(filing.id, {})
      await refreshDisclosures()
      setParseOk(`Parsed filing from ${formatAsOf(filing.report_date)} — new facts appear below.`)
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Parse failed')
    } finally {
      setParsingId(null)
    }
  }

  if (companyLoading || filingsLoading || factsLoading) {
    return <div className="loading">Loading company...</div>
  }

  if (companyError || !company) {
    return <CompanyNotFound ticker={ticker} />
  }

  const registerReady = regUrl.trim() !== '' && regDate !== ''
  const uploadReady = uploadFile !== null && uploadDate !== ''
  const methodologyVersions = Array.from(
    new Set((facts ?? []).map((fact) => fact.methodology_version).filter((v) => v !== '')),
  )

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Disclosures - {company.ticker}</h2>
          <p className="subtitle">{company.name}</p>
          <p className="muted">
            Analyst surface: registry mirrors analyst-supplied sources — nothing is crawled.
            Missing values stay UNKNOWN, never zero.
          </p>
        </div>
      </div>

      <div className="card">
        <h2>Filing registry</h2>
        {filingsError ? (
          <div className="alert alert-error">
            Couldn&apos;t load filings.{' '}
            <button type="button" className="link-btn" onClick={() => refetchFilings()}>
              Retry
            </button>
          </div>
        ) : null}
        {(filings ?? []).length === 0 && !filingsError ? (
          <div className="empty">No filings registered for {company.ticker} yet.</div>
        ) : null}
        {(filings ?? []).length > 0 ? (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Report date</th>
                  <th>Type</th>
                  <th>Basis</th>
                  <th>Bytes</th>
                  <th>Mirrored</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {(filings ?? []).map((filing) => (
                  <FilingRow
                    key={filing.id}
                    filing={filing}
                    parsing={parsingId === filing.id}
                    onParse={handleParse}
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {parseError ? <div className="alert alert-error">{parseError}</div> : null}
        {parseOk ? <div className="alert alert-success">{parseOk}</div> : null}
      </div>

      <div className="card">
        <h2>Register a filing</h2>
        <div className="disclosure-form">
          <label>
            Filing URL
            <input value={regUrl} onChange={(e) => setRegUrl(e.target.value)} placeholder="https://…" />
          </label>
          <label>
            Report date
            <input type="date" value={regDate} onChange={(e) => setRegDate(e.target.value)} />
          </label>
          <label>
            Bulletin ID (optional)
            <input value={regBulletin} onChange={(e) => setRegBulletin(e.target.value)} />
          </label>
          <label>
            Filing type (optional)
            <input value={regType} onChange={(e) => setRegType(e.target.value)} placeholder="annual / quarterly" />
          </label>
          <label>
            Accounting basis (optional)
            <input value={regBasis} onChange={(e) => setRegBasis(e.target.value)} placeholder="EAS / IFRS" />
          </label>
          <label>
            Content hash (optional)
            <input value={regHash} onChange={(e) => setRegHash(e.target.value)} />
          </label>
        </div>
        <button type="button" className="btn btn-primary" disabled={!registerReady || registerBusy} onClick={handleRegister}>
          {registerBusy ? 'Registering…' : 'Register filing'}
        </button>
        {registerError ? <div className="alert alert-error">{registerError}</div> : null}
        {registerOk ? <div className="alert alert-success">{registerOk}</div> : null}
      </div>

      <div className="card">
        <h2>Upload a filing</h2>
        <div className="disclosure-form">
          <label>
            File
            <input
              type="file"
              onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <label>
            Report date
            <input type="date" value={uploadDate} onChange={(e) => setUploadDate(e.target.value)} />
          </label>
          <label>
            Bulletin ID (optional)
            <input value={uploadBulletin} onChange={(e) => setUploadBulletin(e.target.value)} />
          </label>
          <label>
            Filing type (optional)
            <input value={uploadType} onChange={(e) => setUploadType(e.target.value)} placeholder="annual / quarterly" />
          </label>
          <label>
            Accounting basis (optional)
            <input value={uploadBasis} onChange={(e) => setUploadBasis(e.target.value)} placeholder="EAS / IFRS" />
          </label>
        </div>
        <button type="button" className="btn btn-primary" disabled={!uploadReady || uploadBusy} onClick={handleUpload}>
          {uploadBusy ? 'Uploading…' : 'Upload filing'}
        </button>
        {uploadError ? <div className="alert alert-error">{uploadError}</div> : null}
        {uploadOk ? <div className="alert alert-success">{uploadOk}</div> : null}
      </div>

      <div className="card">
        <h2>Facts with provenance</h2>
        {factsError ? (
          <div className="alert alert-error">
            Couldn&apos;t load facts.{' '}
            <button type="button" className="link-btn" onClick={() => refetchFacts()}>
              Retry
            </button>
          </div>
        ) : null}
        {(facts ?? []).length === 0 && !factsError ? (
          <div className="empty">No parsed facts for {company.ticker} yet — parse a filing above.</div>
        ) : null}
        {(facts ?? []).length > 0 ? (
          <div className="table-container">
            <table>
              <caption className="muted">
                Every fact links back to its filing and locator — hover the locator column for full detail.
              </caption>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Value</th>
                  <th>Period</th>
                  <th>Source</th>
                  <th>Locator / extraction</th>
                  <th>EAS tags</th>
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {(facts ?? []).map((fact) => (
                  <FactRow key={fact.id} fact={fact} />
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      <div className="card">
        <h2>Period comparison</h2>
        <div className="disclosure-metric-row">
          <label>
            Metric
            <input value={metricDraft} onChange={(e) => setMetricDraft(e.target.value)} placeholder="revenue" />
          </label>
          <div className="disclosure-presets" role="group" aria-label="Common metrics">
            {METRIC_PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setMetricDraft(preset)
                  setMetric(preset)
                }}
              >
                {preset}
              </button>
            ))}
          </div>
          <button type="button" className="btn btn-primary" onClick={() => setMetric(metricDraft.trim() || 'revenue')}>
            Compare
          </button>
        </div>
        {comparisonLoading ? <p className="muted">Loading comparison…</p> : null}
        {comparisonError ? (
          <div className="alert alert-error">
            {comparisonError instanceof Error ? comparisonError.message : 'Comparison failed.'}{' '}
            Mixed EAS/IFRS bases are never pooled — compare within one basis instead.{' '}
            <button type="button" className="link-btn" onClick={() => refetchComparison()}>
              Retry
            </button>
          </div>
        ) : null}
        {!comparisonLoading && !comparisonError && comparison ? (
          <>
            <h3>TTM / year-on-year deltas</h3>
            <RenderRecord record={comparison.comparison ?? {}} />
            <h3>Margin vs prior year</h3>
            <RenderRecord record={comparison.ttm_margin_vs_prior_year ?? {}} />
            <p className="muted">
              Differences are context for further review under these assumptions — not advice.
            </p>
          </>
        ) : null}
      </div>

      <div className="card">
        <h2>What changed</h2>
        {diffsLoading ? <p className="muted">Loading diffs…</p> : null}
        {diffsError ? (
          <div className="alert alert-error">
            Couldn&apos;t load diffs.{' '}
            <button type="button" className="link-btn" onClick={() => refetchDiffs()}>
              Retry
            </button>
          </div>
        ) : null}
        {!diffsLoading && !diffsError && (diffs ?? []).length === 0 ? (
          <div className="empty">No changes recorded for {company.ticker} yet.</div>
        ) : null}
        {(diffs ?? []).length > 0 ? (
          <div className="table-container">
            <table>
              <caption className="muted">Newest first, old value → new value with delta.</caption>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Kind</th>
                  <th>Prior period</th>
                  <th>Current period</th>
                  <th>Old → new</th>
                  <th>Delta</th>
                </tr>
              </thead>
              <tbody>
                {(diffs ?? []).map((diff) => (
                  <DiffRow key={diff.id} diff={diff} />
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      <p className="muted">
        {methodologyVersions.length > 0
          ? `Fact methodology ${methodologyVersions.map((v) => `v${v}`).join(', ')}.`
          : 'No fact methodology recorded yet.'}{' '}
        Sources are mirrored filings listed above; report dates are the as-of for each figure.
      </p>
    </div>
  )
}
