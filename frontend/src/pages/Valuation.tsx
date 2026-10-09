import "./Valuation.css";

import { useParams } from 'react-router-dom'
import { useCompanyByTicker } from '../api/client'

export default function Valuation() {
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
      <h1>Valuation - {company.ticker}</h1>
      <h2>{company.name}</h2>

      <div className="valuation-info">
        <p>
          <strong>Note:</strong> Valuations are based on explicit assumptions
          and deterministic formulas. Results should be interpreted with
          understanding of the underlying assumptions.
        </p>
      </div>

      <div className="valuation-models">
        <h3>Supported Models</h3>
        <ul>
          <li><strong>P/E Valuation:</strong> Price = EPS × P/E Ratio</li>
          <li><strong>P/B Valuation:</strong> Price = BVPS × P/B Ratio</li>
          <li><strong>EV/EBITDA:</strong> Price = (EBITDA × EV/EBITDA - Net Debt) / Shares</li>
          <li><strong>DCF:</strong> Discounted Cash Flow with terminal value</li>
        </ul>
      </div>

      <div className="empty-state">
        To calculate valuations, use the API endpoint:
        <code>POST /api/valuation/companies/{company.id}/calculate</code>
      </div>
    </div>
  )
}
