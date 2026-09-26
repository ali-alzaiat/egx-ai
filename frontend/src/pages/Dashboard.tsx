import { useHealthCheck } from '../api/client'

export default function Dashboard() {
  const { data: health, isLoading, error } = useHealthCheck()

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>EGX Stock Analysis & Shariah Screening Platform</p>
      </div>

      <div className="card-grid">
        <div className="card">
          <div className="card-label">System Status</div>
          {isLoading && <div className="card-value">Loading...</div>}
          {error && <div className="card-value negative">Offline</div>}
          {health && (
            <>
              <div className="card-value positive">{health.status}</div>
              <div className="card-subtitle">Version {health.version}</div>
            </>
          )}
        </div>

        <div className="card">
          <div className="card-label">EGX Companies</div>
          <div className="card-value">--</div>
          <div className="card-subtitle">Phase 2 will populate</div>
        </div>

        <div className="card">
          <div className="card-label">Shariah Universe</div>
          <div className="card-value">--</div>
          <div className="card-subtitle">Phase 4 will populate</div>
        </div>

        <div className="card">
          <div className="card-label">Valuation Opportunities</div>
          <div className="card-value">--</div>
          <div className="card-subtitle">Phase 5 will populate</div>
        </div>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Company</th>
              <th>Sector</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                No data yet. Ingestion layer coming in Phase 2.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
