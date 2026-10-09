import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useCompanies, useScreenedCompanies } from '../api/client'
import type { Company, ScreenedCompanySummary } from '../types'
import { formatAsOf } from '../lib/format'

// Global navigation destination for Shariah screening (R17 F2). Screening is
// run per company from its overview tab; this page lists what has been run.
export default function Screening() {
  const { data: screened, isLoading, error, refetch } = useScreenedCompanies()
  // The screening list carries company_id only; resolve tickers via the full
  // universe (page_size caps at 200, so two pages cover all 229).
  const { data: universePage1 } = useCompanies({ page_size: 200 })
  const { data: universePage2 } = useCompanies({ page_size: 200, page: 2 })

  const byId = useMemo(() => {
    const map = new Map<string, Company>()
    for (const company of [
      ...(universePage1?.items ?? []),
      ...(universePage2?.items ?? []),
    ]) {
      map.set(company.id, company)
    }
    return map
  }, [universePage1, universePage2])

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Shariah Screening</h1>
          <p className="subtitle">
            Financial-ratio screening of EGX companies against a versioned
            methodology. Results are research input, not a certification.
          </p>
        </div>
        <Link to="/companies" className="btn btn-secondary">
          Browse companies
        </Link>
      </div>

      <div className="card">
        <h2 className="section-title">Screened companies</h2>
        {isLoading && <div className="loading">Loading screening results...</div>}
        {error && (
          <div className="alert alert-error">
            Couldn't load screening results.{' '}
            <button className="link-btn" onClick={() => refetch()}>
              Retry
            </button>
          </div>
        )}
        {screened && screened.length === 0 && (
          <div className="empty">
            No companies have been screened yet. Open a company and run
            screening from its page.
          </div>
        )}
        {screened && screened.length > 0 && (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Verdict</th>
                  <th>Screened at</th>
                  <th>Methodology</th>
                </tr>
              </thead>
              <tbody>
                {screened.map((s: ScreenedCompanySummary) => {
                  const company = byId.get(s.company_id)
                  return (
                    <tr key={s.id}>
                      <td>
                        {company ? (
                          <Link
                            to={`/companies/${company.ticker}/screening`}
                            className="ticker-link"
                          >
                            {company.ticker}
                          </Link>
                        ) : (
                          s.company_id
                        )}
                      </td>
                      <td>{s.status.replace('_', ' ')}</td>
                      <td>{formatAsOf(s.screened_at)}</td>
                      <td>v{s.methodology_version}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <p className="disclaimer">
              Verdicts are tied to the methodology version shown and the
              statements recorded at screening time.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}