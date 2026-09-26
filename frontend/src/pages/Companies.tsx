import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useCompanies } from '../api/client'

export default function Companies() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sectorFilter, setSectorFilter] = useState('')

  const { data, isLoading, error } = useCompanies({
    page,
    page_size: 20,
    search: search || undefined,
    status: statusFilter || undefined,
    sector: sectorFilter || undefined,
  })

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
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
          className="filter-input"
        />
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value)
            setPage(1)
          }}
          className="filter-select"
        >
          <option value="">All Status</option>
          <option value="ACTIVE">Active</option>
          <option value="SUSPENDED">Suspended</option>
          <option value="DELISTED">Delisted</option>
        </select>
        <select
          value={sectorFilter}
          onChange={(e) => {
            setSectorFilter(e.target.value)
            setPage(1)
          }}
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

      {isLoading && <div className="loading">Loading...</div>}
      {error && <div className="loading">Error loading companies</div>}

      {data && (
        <>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Name</th>
                  <th>Sector</th>
                  <th>Industry</th>
                  <th>Status</th>
                  <th>Currency</th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                      No companies found
                    </td>
                  </tr>
                ) : (
                  data.items.map((company) => (
                    <tr key={company.id}>
                      <td>
                        <Link to={`/companies/${company.ticker}`} className="ticker-link">
                          {company.ticker}
                        </Link>
                      </td>
                      <td>{company.name}</td>
                      <td>{company.sector || '--'}</td>
                      <td>{company.industry || '--'}</td>
                      <td>
                        <span className={`status-badge ${company.status.toLowerCase()}`}>
                          {company.status}
                        </span>
                      </td>
                      <td>{company.currency}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {data.total_pages > 1 && (
            <div className="pagination">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="pagination-btn"
              >
                Previous
              </button>
              <span className="pagination-info">
                Page {page} of {data.total_pages} ({data.total} companies)
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
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
