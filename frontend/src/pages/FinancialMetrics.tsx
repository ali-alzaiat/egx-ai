import "./FinancialMetrics.css";

import { useParams } from 'react-router-dom'
import { useCompanyByTicker, useCompanyMetrics } from '../api/client'
import type { FinancialMetric } from '../types'

function MetricValue({ metric }: { metric: FinancialMetric }) {
  if (metric.status === 'INSUFFICIENT_DATA') {
    return <span className="metric-na">Insufficient Data</span>
  }
  if (metric.status === 'NOT_APPLICABLE') {
    return <span className="metric-na">N/A</span>
  }
  if (metric.status === 'INVALID') {
    return <span className="metric-invalid">Invalid</span>
  }
  if (metric.value === null) {
    return <span className="metric-na">--</span>
  }

  const value = parseFloat(metric.value)
  let displayValue: string

  if (metric.unit === '%') {
    displayValue = `${value.toFixed(2)}%`
  } else if (metric.unit === 'ratio') {
    displayValue = value.toFixed(4)
  } else if (metric.unit === 'currency per share') {
    displayValue = `EGP ${value.toFixed(4)}`
  } else {
    displayValue = value.toLocaleString(undefined, { maximumFractionDigits: 2 })
  }

  return (
    <span className="metric-value" title={metric.reason || undefined}>
      {displayValue}
    </span>
  )
}

function MetricCard({ metric }: { metric: FinancialMetric }) {
  return (
    <div className="metric-card">
      <div className="metric-header">
        <span className="metric-name">{metric.display_name}</span>
        <span className={`metric-status status-${metric.status.toLowerCase()}`}>
          {metric.status}
        </span>
      </div>
      <div className="metric-body">
        <MetricValue metric={metric} />
      </div>
      {metric.reason && (
        <div className="metric-footer">
          <span className="metric-reason">{metric.reason}</span>
        </div>
      )}
    </div>
  )
}

export default function FinancialMetrics() {
  const { ticker } = useParams<{ ticker: string }>()
  const { data: company, isLoading: companyLoading } = useCompanyByTicker(ticker)

  const { data: metrics, isLoading: metricsLoading } = useCompanyMetrics(company?.id)

  if (companyLoading || metricsLoading) {
    return <div className="loading">Loading financial metrics...</div>
  }

  if (!company) {
    return <div className="error">Company not found</div>
  }

  if (!metrics || metrics.length === 0) {
    return (
      <div className="page">
        <h1>Financial Metrics - {company.ticker}</h1>
        <h2>{company.name}</h2>
        <div className="empty-state">
          No metrics calculated yet. Use the calculate endpoint to generate metrics.
        </div>
      </div>
    )
  }

  // Group metrics by category
  const categories = {
    growth: metrics.filter(m => m.metric_code.includes('growth')),
    margins: metrics.filter(m => m.metric_code.includes('margin')),
    profitability: metrics.filter(m => ['roe', 'roa'].includes(m.metric_code)),
    leverage: metrics.filter(m => m.metric_code.includes('debt')),
    liquidity: metrics.filter(m => ['current_ratio', 'quick_ratio'].includes(m.metric_code)),
    cashFlow: metrics.filter(m => m.metric_code.includes('cash_flow') || m.metric_code === 'free_cash_flow'),
    perShare: metrics.filter(m => m.metric_code === 'eps' || m.metric_code === 'book_value_per_share'),
  }

  return (
    <div className="page">
      <h1>Financial Metrics - {company.ticker}</h1>
      <h2>{company.name}</h2>

      <div className="metrics-grid">
        {categories.growth.length > 0 && (
          <section className="metrics-section">
            <h3>Growth</h3>
            <div className="metrics-list">
              {categories.growth.map(metric => (
                <MetricCard key={metric.metric_code} metric={metric} />
              ))}
            </div>
          </section>
        )}

        {categories.margins.length > 0 && (
          <section className="metrics-section">
            <h3>Margins</h3>
            <div className="metrics-list">
              {categories.margins.map(metric => (
                <MetricCard key={metric.metric_code} metric={metric} />
              ))}
            </div>
          </section>
        )}

        {categories.profitability.length > 0 && (
          <section className="metrics-section">
            <h3>Profitability</h3>
            <div className="metrics-list">
              {categories.profitability.map(metric => (
                <MetricCard key={metric.metric_code} metric={metric} />
              ))}
            </div>
          </section>
        )}

        {categories.leverage.length > 0 && (
          <section className="metrics-section">
            <h3>Leverage</h3>
            <div className="metrics-list">
              {categories.leverage.map(metric => (
                <MetricCard key={metric.metric_code} metric={metric} />
              ))}
            </div>
          </section>
        )}

        {categories.liquidity.length > 0 && (
          <section className="metrics-section">
            <h3>Liquidity</h3>
            <div className="metrics-list">
              {categories.liquidity.map(metric => (
                <MetricCard key={metric.metric_code} metric={metric} />
              ))}
            </div>
          </section>
        )}

        {categories.cashFlow.length > 0 && (
          <section className="metrics-section">
            <h3>Cash Flow</h3>
            <div className="metrics-list">
              {categories.cashFlow.map(metric => (
                <MetricCard key={metric.metric_code} metric={metric} />
              ))}
            </div>
          </section>
        )}

        {categories.perShare.length > 0 && (
          <section className="metrics-section">
            <h3>Per Share</h3>
            <div className="metrics-list">
              {categories.perShare.map(metric => (
                <MetricCard key={metric.metric_code} metric={metric} />
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
