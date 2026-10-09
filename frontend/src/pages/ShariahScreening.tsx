import "./ShariahScreening.css";

import { useParams } from 'react-router-dom'
import { useCompanyByTicker } from '../api/client'

export default function ShariahScreening() {
  const { ticker } = useParams<{ ticker: string }>()
  const { data: company, isLoading: companyLoading } = useCompanyByTicker(ticker)

  if (companyLoading) {
    return <div className="loading">Loading company...</div>
  }

  if (!company) {
    return <div className="error">Company not found</div>
  }

  return (
    <div className="page">
      <h1>Shariah Screening - {company.ticker}</h1>
      <h2>{company.name}</h2>

      <div className="screening-info">
        <p>
          <strong>Note:</strong> This is a screening tool, not a certification.
          Results are based on financial ratio analysis and should be verified
          with qualified Shariah scholars.
        </p>
      </div>

      <div className="methodology-info">
        <h3>Methodology</h3>
        <p>
          <strong>Source:</strong> AAOIFI Shariah Standard No. 21 (Financial Papers)
        </p>
        <p>
          <strong>Version:</strong> 1.0
        </p>
        <div className="thresholds">
          <h4>Thresholds</h4>
          <ul>
            <li>Debt/Assets: &lt; 33%</li>
            <li>Interest Income/Revenue: &lt; 5%</li>
            <li>Cash & Securities/Assets: &lt; 33%</li>
          </ul>
        </div>
      </div>

      <div className="prohibited-industries">
        <h3>Prohibited Industries</h3>
        <ul>
          <li>Alcohol</li>
          <li>Gambling</li>
          <li>Pork</li>
          <li>Tobacco</li>
          <li>Adult Entertainment</li>
          <li>Weapons</li>
          <li>Conventional Banking</li>
          <li>Conventional Insurance</li>
        </ul>
      </div>

      <div className="empty-state">
        To screen this company, use the API endpoint:
        <code>POST /api/screening/companies/{company.id}/screen</code>
      </div>
    </div>
  )
}
