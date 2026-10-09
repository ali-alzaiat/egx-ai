import { Link } from 'react-router-dom'

// Shared 404 state for every company view (F15): echo the ticker the user
// typed, give two ways back, and never re-request the company.
export default function CompanyNotFound({ ticker }: { ticker?: string }) {
  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>We couldn't find a company with ticker "{ticker}"</h1>
          <p className="subtitle">
            Check the ticker — EGX tickers are 2–6 letters, e.g. COMI.
          </p>
        </div>
      </div>
      <div className="company-actions">
        <Link to="/companies" className="btn btn-secondary">
          Browse companies
        </Link>
        <Link
          to={`/companies?search=${encodeURIComponent(ticker ?? '')}`}
          className="btn btn-secondary"
        >
          Search another ticker
        </Link>
      </div>
    </div>
  )
}