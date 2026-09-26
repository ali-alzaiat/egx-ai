import { useParams } from 'react-router-dom'
import { useCompanyByTicker } from '../api/client'

export default function TechnicalAnalysis() {
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
      <h1>Technical Analysis - {company.ticker}</h1>
      <h2>{company.name}</h2>

      <div className="technical-info">
        <p>
          <strong>Note:</strong> Technical indicators are calculated deterministically
          from price data. They should be used as part of a comprehensive analysis,
          not as standalone trading signals.
        </p>
      </div>

      <div className="indicators-list">
        <h3>Supported Indicators</h3>
        <ul>
          <li><strong>SMA:</strong> Simple Moving Average</li>
          <li><strong>EMA:</strong> Exponential Moving Average</li>
          <li><strong>RSI:</strong> Relative Strength Index (14-period)</li>
          <li><strong>MACD:</strong> Moving Average Convergence Divergence</li>
          <li><strong>Bollinger Bands:</strong> Volatility indicator</li>
          <li><strong>OBV:</strong> On-Balance Volume</li>
          <li><strong>VWAP:</strong> Volume Weighted Average Price</li>
        </ul>
      </div>

      <div className="empty-state">
        To calculate indicators, use the API endpoint:
        <code>POST /api/technical/companies/{company.id}/calculate</code>
      </div>
    </div>
  )
}
