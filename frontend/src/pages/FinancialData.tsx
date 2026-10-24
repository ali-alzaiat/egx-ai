import "./FinancialData.css";

import { Link, useParams } from 'react-router-dom'
import { useCompanyByTicker, useFinancialPeriods, useFinancialFacts } from '../api/client'
import CompanyNotFound from '../components/CompanyNotFound'

export default function FinancialData() {
  const { ticker } = useParams<{ ticker: string }>()
  const { data: company, isLoading: companyLoading, error: companyError } = useCompanyByTicker(ticker)
  const {
    data: periods,
    isLoading: periodsLoading,
    error: periodsError,
    refetch: refetchPeriods,
  } = useFinancialPeriods(company?.id)
  const { data: incomeFacts, error: incomeError } = useFinancialFacts(company?.id, { fact_type: 'INCOME_STATEMENT' })
  const { data: balanceFacts, error: balanceError } = useFinancialFacts(company?.id, { fact_type: 'BALANCE_SHEET' })
  const { data: cashFlowFacts, error: cashFlowError } = useFinancialFacts(company?.id, { fact_type: 'CASH_FLOW' })

  if (companyLoading || periodsLoading) {
    return <div className="loading">Loading financial data...</div>
  }

  if (companyError || !company) {
    return <CompanyNotFound ticker={ticker} />
  }

  const loadError = periodsError || incomeError || balanceError || cashFlowError
  if (loadError) {
    return (
      <div className="page">
        <div className="page-header">
          <div>
            <h2>Financial Data - {company.ticker}</h2>
            <p className="subtitle">{company.name}</p>
          </div>
        </div>
        <div className="alert alert-error">
          Couldn't load financial data.{' '}
          <button className="link-btn" onClick={() => refetchPeriods()}>
            Retry
          </button>
        </div>
      </div>
    )
  }

  const hasPeriods = (periods?.length ?? 0) > 0
  const hasIncome = (incomeFacts?.length ?? 0) > 0
  const hasBalance = (balanceFacts?.length ?? 0) > 0
  const hasCashFlow = (cashFlowFacts?.length ?? 0) > 0
  const allEmpty = !hasPeriods && !hasIncome && !hasBalance && !hasCashFlow

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Financial Data - {company.ticker}</h2>
          <p className="subtitle">{company.name}</p>
        </div>
        <Link className="btn btn-secondary" to={`/companies/${company.ticker}/thesis#filings`}>
          Disclosures
        </Link>
      </div>


      {allEmpty && (
        <div className="empty">
          No financial data recorded for {company.ticker}. Statements appear
          here once filings have been ingested for this company.
        </div>
      )}

      {!allEmpty && (
        <>
          <section className="section">
            <h3>Reporting Periods</h3>
            {hasPeriods ? (
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
                  {periods!.map((period) => (
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
              <p className="muted">No reporting periods recorded for {company.ticker} yet.</p>
            )}
          </section>

          <section className="section">
            <h3>Income Statement</h3>
            {hasIncome ? (
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
                  {incomeFacts!.map((fact) => (
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
              <p className="muted">No income statement facts recorded for {company.ticker} yet.</p>
            )}
          </section>

          <section className="section">
            <h3>Balance Sheet</h3>
            {hasBalance ? (
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
                  {balanceFacts!.map((fact) => (
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
              <p className="muted">No balance sheet facts recorded for {company.ticker} yet.</p>
            )}
          </section>

          <section className="section">
            <h3>Cash Flow</h3>
            {hasCashFlow ? (
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
                  {cashFlowFacts!.map((fact) => (
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
              <p className="muted">No cash flow facts recorded for {company.ticker} yet.</p>
            )}
          </section>
        </>
      )}
    </div>
  )
}
