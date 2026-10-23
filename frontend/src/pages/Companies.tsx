import "./Companies.css";

/*
 * Companies radar (Task 12): dense sortable table replacing the plain
 * list. Per-row data sources are wired through the existing hooks —
 * no new API client functions:
 *   stance value  → useStanceRadar (batch), reasons → useStance (per row)
 *   price as-of   → useLatestPrice (per row)
 *   score/tier/coverage → useSignals (single batch)
 *   shariah       → useScreenedCompanies (single batch)
 *   gross margin  → useRatios (per row, code "gross_margin")
 * Missing data renders as "—" with an INSUFFICIENT_DATA note — never zero.
 */

import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  useCompanies,
  useLatestPrice,
  useRatios,
  useScreenedCompanies,
  useSignals,
  useStance,
  useStanceRadar,
} from '../api/client'
import type {
  MarketSignal,
  ScreenedCompanySummary,
  StanceRadarItem,
  StanceResult,
} from '../types'
import { debounce } from '../lib/debounce'
import { sortRadarRows, type RadarSortDir, type RadarSortKey } from './companies/radarSort'

interface RadarRow {
  companyId: string
  ticker: string
  name: string
  stance: string | null
  score: number | null
  tier: string | null
  shariah: string | null
  coverage: number | null
}

const SORTABLE_COLUMNS: { key: RadarSortKey; label: string; defaultDir: RadarSortDir }[] = [
  { key: 'ticker', label: 'Ticker / Name', defaultDir: 'asc' },
  { key: 'stance', label: 'Stance', defaultDir: 'asc' },
  { key: 'score', label: 'Score', defaultDir: 'desc' },
  { key: 'tier', label: 'Tier', defaultDir: 'desc' },
  { key: 'shariah', label: 'Shariah', defaultDir: 'asc' },
  { key: 'coverage', label: 'Coverage', defaultDir: 'desc' },
]

export default function Companies() {
  const [searchParams, setSearchParams] = useSearchParams()
  const search = searchParams.get('search') ?? ''
  const sectorFilter = searchParams.get('sector') ?? ''
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1)

  const [draft, setDraft] = useState(search)
  const [sortKey, setSortKey] = useState<RadarSortKey>('ticker')
  const [sortDir, setSortDir] = useState<RadarSortDir>('asc')

  // External navigation (e.g. "Search another ticker") writes ?search=
  // directly; pick it up. While typing, the URL only ever holds what the
  // draft already holds, so this is a no-op there.
  useEffect(() => {
    setDraft(search)
  }, [search])

  const setParam = (key: string, value: string | null): void => {
    const next = new URLSearchParams(searchParams)
    if (value === null || value === '') {
      next.delete(key)
    } else {
      next.set(key, value)
    }
    if (key !== 'page') next.delete('page')
    setSearchParams(next)
  }

  // Debounce URL writes so one query fires per search pause, not per keystroke.
  const debouncedSearch = useMemo(
    () =>
      debounce((value: string) => {
        setParam('search', value || null)
      }, 300),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searchParams.toString()],
  )

  const { data, isLoading, error, refetch } = useCompanies({
    page,
    page_size: 20,
    search: search || undefined,
    sector: sectorFilter || undefined,
  })
  // Universe total for the coverage note, independent of the active filter.
  const { data: universe } = useCompanies({ page_size: 1 })
  const universeTotal = universe?.total ?? data?.total ?? 0

  // ── Radar enrichment (batch hooks keyed for row lookup) ────────────────
  const { data: radar } = useStanceRadar()
  const stanceByTicker = useMemo(() => {
    const map = new Map<string, StanceRadarItem>()
    for (const item of radar?.items ?? []) map.set(item.ticker, item)
    return map
  }, [radar])

  const { data: signals } = useSignals({ limit: 500 })
  const signalByTicker = useMemo(() => {
    const map = new Map<string, MarketSignal>()
    for (const signal of signals?.results ?? []) map.set(signal.ticker, signal)
    return map
  }, [signals])

  const { data: screened } = useScreenedCompanies()
  const screenByCompanyId = useMemo(() => {
    const map = new Map<string, ScreenedCompanySummary>()
    for (const summary of screened ?? []) map.set(summary.company_id, summary)
    return map
  }, [screened])

  const rows = useMemo<RadarRow[]>(() => {
    const items = data?.items ?? []
    return items.map((company) => {
      const signal = signalByTicker.get(company.ticker) ?? null
      const summary = screenByCompanyId.get(company.id) ?? null
      return {
        companyId: company.id,
        ticker: company.ticker,
        name: company.name,
        stance: stanceByTicker.get(company.ticker)?.stance ?? null,
        score: signal?.score ?? null,
        tier: signal?.tier ?? null,
        shariah: summary?.status ?? null,
        coverage: signal?.data_coverage ?? null,
      }
    })
  }, [data, stanceByTicker, signalByTicker, screenByCompanyId])

  const sortedRows = useMemo(
    () => sortRadarRows(rows, sortKey, sortDir),
    [rows, sortKey, sortDir],
  )

  const toggleSort = (column: { key: RadarSortKey; defaultDir: RadarSortDir }): void => {
    if (column.key === sortKey) {
      setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(column.key)
      setSortDir(column.defaultDir)
    }
  }

  const clearFilters = (): void => {
    setDraft('')
    setSearchParams({})
  }

  const coverageNote = (): string => {
    const total = data?.total ?? 0
    if (search) {
      return `Showing ${total} matches for "${search}" of ${universeTotal} companies`
    }
    if (sectorFilter) {
      const excluded = universeTotal - total
      return `Showing ${total} of ${universeTotal} companies · ${excluded} excluded by this filter.`
    }
    return `Showing ${universeTotal} companies`
  }

  return (
    <div>
      <div className="page-header">
        <h1>Companies</h1>
        <p>EGX-listed companies</p>
      </div>

      <div className="filters">
        <input
          type="text"
          placeholder="Search ticker or name..."
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value)
            debouncedSearch(e.target.value)
          }}
          className="filter-input"
        />
        <select
          value={sectorFilter}
          onChange={(e) => setParam('sector', e.target.value || null)}
          className="filter-select"
        >
          <option value="">All Sectors</option>
          <option value="Financials">Financials</option>
          <option value="Consumer Staples">Consumer Staples</option>
          <option value="Industrials">Industrials</option>
          <option value="Communication Services">Communication Services</option>
          <option value="Consumer Discretionary">Consumer Discretionary</option>
          <option value="Real Estate">Real Estate</option>
        </select>
      </div>

      {data && <p className="muted">{coverageNote()}</p>}

      {isLoading && <div className="loading">Loading companies...</div>}
      {error && (
        <div className="alert alert-error">
          Couldn't load companies.{' '}
          <button className="link-btn" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="empty">
          No companies match these filters.{' '}
          <button className="link-btn" onClick={clearFilters}>
            Clear filters
          </button>
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="table-container">
            <table className="radar-table">
              <thead>
                <tr>
                  {SORTABLE_COLUMNS.map((column) => (
                    <th
                      key={column.key}
                      aria-sort={
                        sortKey === column.key
                          ? sortDir === 'asc'
                            ? 'ascending'
                            : 'descending'
                          : 'none'
                      }
                    >
                      <button
                        type="button"
                        className="radar-sort-btn"
                        onClick={() => toggleSort(column)}
                      >
                        {column.label}
                        {sortKey === column.key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
                      </button>
                    </th>
                  ))}
                  <th>Price as-of</th>
                  <th>
                    Gross margin{' '}
                    <span className="muted radar-header-note">no data</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row) => (
                  <tr key={row.companyId}>
                    <td>
                      <Link to={`/companies/${row.ticker}`} className="ticker-link">
                        {row.ticker}
                      </Link>
                      <div className="radar-name">{row.name}</div>
                    </td>
                    <td>
                      <StanceCell ticker={row.ticker} stance={row.stance} />
                    </td>
                    <td>
                      <PriceAsOfCell companyId={row.companyId} />
                    </td>
                    <td className="num">
                      {row.score !== null ? row.score.toFixed(1) : <MissingDash label="no score" />}
                    </td>
                    <td>{row.tier ? <TierBadge tier={row.tier} /> : <MissingDash label="no tier" />}</td>
                    <td>
                      {row.shariah ? (
                        <ShariahBadge status={row.shariah} />
                      ) : (
                        <MissingDash label="not screened" />
                      )}
                    </td>
                    <td>
                      <GrossMarginCell ticker={row.ticker} />
                    </td>
                    <td>
                      <CoverageCell coverage={row.coverage} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.total_pages > 1 && (
            <div className="pagination">
              <button
                onClick={() => setParam('page', String(page - 1))}
                disabled={page === 1}
                className="pagination-btn"
              >
                Previous
              </button>
              <span className="pagination-info">
                Page {page} of {data.total_pages} ({data.total} companies)
              </span>
              <button
                onClick={() => setParam('page', String(page + 1))}
                disabled={page === data.total_pages}
                className="pagination-btn"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

/** Shared missing-value rendering: dash, not zero, with an honest tooltip. */
function MissingDash({ label }: { label: string }) {
  return (
    <span className="radar-missing" title={`INSUFFICIENT_DATA — ${label}`}>
      —
    </span>
  )
}

/*
 * Note on data sources (kept honest, per the task brief):
 * - Stance value comes from the radar batch; the reason summary in the
 *   tooltip comes from the per-company stance fetch (the radar payload has
 *   no reasons field).
 * - Gross margin is wired through the existing per-ticker ratios hook.
 * When a fetch fails or the value is missing, the cell renders a dash with
 * an INSUFFICIENT_DATA note — never a zero.
 */
function StanceCell({ ticker, stance }: { ticker: string; stance: string | null }) {
  // Reason summary only; the badge itself renders immediately from the radar item.
  const { data: stanceResult } = useStance(stance ? ticker : undefined)

  if (!stance) {
    return <MissingDash label="stance absent or stance fetch failed" />
  }
  const shape = STANCE_SHAPES[stance] ?? '○'
  const className = STANCE_CLASSES[stance] ?? 'radar-stance-neutral'
  const title = stanceResult
    ? stanceSummary(stanceResult)
    : `Confidence pending — full reasons on the company Signals tab`
  return (
    <span className={`radar-stance ${className}`} title={title}>
      {shape} {stance.toUpperCase()}
    </span>
  )
}

const STANCE_SHAPES: Record<string, string> = {
  buy: '▲',
  hold: '●',
  reduce: '▼',
}

const STANCE_CLASSES: Record<string, string> = {
  buy: 'radar-stance-buy',
  hold: 'radar-stance-hold',
  reduce: 'radar-stance-reduce',
}

function stanceSummary(result: StanceResult): string {
  const lines = result.reasons.map((r) => `${r.engine}: ${r.text}`)
  return [`${result.stance.toUpperCase()} · confidence ${result.confidence}/100`, ...lines].join('\n')
}

function TierBadge({ tier }: { tier: string }) {
  return (
    <span className={`tier-badge tier-${tier.toLowerCase()}`} title={`Signal tier: ${tier}`}>
      {tier}
    </span>
  )
}

function ShariahBadge({ status }: { status: string }) {
  if (status === 'COMPLIANT') {
    return (
      <span className="radar-shariah radar-shariah-ok" title="Shariah screening: compliant">
        ✓ compliant
      </span>
    )
  }
  if (status === 'NON_COMPLIANT') {
    return (
      <span className="radar-shariah radar-shariah-non" title="Shariah screening: non-compliant">
        ✕ non-compliant
      </span>
    )
  }
  return <MissingDash label={`shariah status ${status}`} />
}

function CoverageCell({ coverage }: { coverage: number | null }) {
  if (coverage === null) {
    return <MissingDash label="no signal coverage" />
  }
  const pct = Math.round(coverage * 100)
  const shape = coverage >= 0.9 ? '●' : coverage >= 0.5 ? '◐' : '○'
  return (
    <span className="radar-coverage" title={`Price-history data coverage: ${pct}%`}>
      {shape} {pct}%
    </span>
  )
}

function PriceAsOfCell({ companyId }: { companyId: string }) {
  const { data } = useLatestPrice(companyId)
  if (!data) {
    return <MissingDash label="no stored price" />
  }
  return (
    <span className="radar-price" title={`Close ${data.close} on ${data.date}`}>
      {data.close}
      <span className="radar-price-date">{data.date}</span>
    </span>
  )
}

function GrossMarginCell({ ticker }: { ticker: string }) {
  const { data, isLoading, error } = useRatios(ticker)
  const margin = data?.find((ratio) => ratio.code === 'gross_margin')
  if (margin && margin.status === 'AVAILABLE') {
    if (margin.value !== null) {
      return (
        <span className="num">{`${(Number.parseFloat(margin.value) * 100).toFixed(1)}%`}</span>
      )
    }
    return <MissingDash label={margin.reason ?? 'gross margin missing'} />
  }
  if (isLoading || error || !margin) {
    return <MissingDash label="gross margin not available (no data)" />
  }
  return <MissingDash label={margin.reason ?? 'gross margin insufficient'} />
}
