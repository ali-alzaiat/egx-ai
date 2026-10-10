import "./Companies.css";

import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useCompanies } from '../api/client'
import { debounce } from '../lib/debounce'

export default function Companies() {
  const [searchParams, setSearchParams] = useSearchParams()
  const search = searchParams.get('search') ?? ''
  const sectorFilter = searchParams.get('sector') ?? ''
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1)

  const [draft, setDraft] = useState(search)

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
            <table>
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Name</th>
                  <th>Sector</th>
                  <th>Industry</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((company) => (
                  <tr key={company.id}>
                    <td>
                      <Link to={`/companies/${company.ticker}`} className="ticker-link">
                        {company.ticker}
                      </Link>
                    </td>
                    <td>{company.name}</td>
                    <td>
                      {company.sector || (
                        <span title="Sector not recorded">—</span>
                      )}
                    </td>
                    <td>{company.industry || '—'}</td>
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
