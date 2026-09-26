import { useParams } from 'react-router-dom'
import { useCompanyByTicker, useFinancialPeriods, useFinancialFacts } from '../api/client'

export default function FinancialData() {
  const { ticker } = useParams<{ ticker: string }>()
  const { data: company, isLoading: companyLoading } = useCompanyByTicker(ticker)
  const { data: periods, isLoading: periodsLoading } = useFinancialPeriods(company?.id)
  const { data: incomeFacts } = useFinancialFacts(company?.id, { fact_type: 'INCOME_STATEMENT' })
  const { data: balanceFacts } = useFinancialFacts(company?.id, { fact_type: 'BALANCE_SHEET' })
  const { data: cashFlowFacts } = useFinancialFacts(company?.id, { fact_type: 'CASH_FLOW' })

  if (companyLoading || periodsLoading) {
    return <div className="loading">Loading financial data...</div>
  }

  if (!company) {
    return <div className="error">Company not found</div>
  }

  return (
    <div className="page">
      <h1>Financial Data - {company.ticker}</h1>
      <h2>{company.name}</h2>

      <section className="section">
        <h3>Reporting Periods</h3>
        {periods && periods.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Fiscal Year</th>
                <th>Start Date</th>
                <th>End Date</th>
              </tr>
            </thead>
            <tbody>
              {periods.map((period) => (
                <tr key={period.id}>
                  <td>{period.period_type}</td>
                  <td>{period.fiscal_year}</td>
                  <td>{period.start_date}</td>
                  <td>{period.end_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No financial periods available</p>
        )}
      </section>

      <section className="section">
        <h3>Income Statement</h3>
        {incomeFacts && incomeFacts.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Label</th>
                <th>Value</th>
                <th>Currency</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {incomeFacts.map((fact) => (
                <tr key={fact.id}>
                  <td>{fact.normalized_label || fact.reported_label}</td>
                  <td>{fact.normalized_value || fact.reported_value}</td>
                  <td>{fact.currency}</td>
                  <td className={`status-${fact.status.toLowerCase()}`}>{fact.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No income statement data available</p>
        )}
      </section>

      <section className="section">
        <h3>Balance Sheet</h3>
        {balanceFacts && balanceFacts.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Label</th>
                <th>Value</th>
                <th>Currency</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {balanceFacts.map((fact) => (
                <tr key={fact.id}>
                  <td>{fact.normalized_label || fact.reported_label}</td>
                  <td>{fact.normalized_value || fact.reported_value}</td>
                  <td>{fact.currency}</td>
                  <td className={`status-${fact.status.toLowerCase()}`}>{fact.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No balance sheet data available</p>
        )}
      </section>

      <section className="section">
        <h3>Cash Flow</h3>
        {cashFlowFacts && cashFlowFacts.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Label</th>
                <th>Value</th>
                <th>Currency</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {cashFlowFacts.map((fact) => (
                <tr key={fact.id}>
                  <td>{fact.normalized_label || fact.reported_label}</td>
                  <td>{fact.normalized_value || fact.reported_value}</td>
                  <td>{fact.currency}</td>
                  <td className={`status-${fact.status.toLowerCase()}`}>{fact.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No cash flow data available</p>
        )}
      </section>
    </div>
  )
}
