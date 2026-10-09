import { useParams, Link } from 'react-router-dom'
import { useCompanyByTicker, useCompanyPrices, useLatestPrice } from '../api/client'
import DataQualityCard from '../components/DataQualityCard'

export default function CompanyDetail() {
  const { ticker } = useParams<{ ticker: string }>()
  const { data: company, isLoading: loadingCompany, error: errorCompany } = useCompanyByTicker(ticker)

  const { data: latestPrice } = useLatestPrice(company?.id)

  const oneYearAgo = new Date()
  oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1)
  const startDate = oneYearAgo.toISOString().split('T')[0]!

  const { data: pricesData, isLoading: loadingPrices } = useCompanyPrices(company?.id, {
    start_date: startDate,
    page_size: 365,
  })

  if (loadingCompany) return <div className="loading">Loading company...</div>
  if (errorCompany) return <div className="loading">Company not found</div>
  if (!company) return <div className="loading">Company not found</div>

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>{company.ticker} — {company.name}</h1>
          {company.name_ar && <p className="subtitle">{company.name_ar}</p>}
        </div>
        <div className="company-actions">
          <Link to={`/companies/${ticker}/financials`} className="btn btn-primary">Financial Data</Link>
          <Link to={`/companies/${ticker}/metrics`} className="btn btn-primary">Metrics</Link>
          <Link to={`/companies/${ticker}/technical`} className="btn btn-primary">Technical</Link>
          <Link to={`/companies/${ticker}/ai`} className="btn btn-primary">AI Insights</Link>
        </div>
      </div>

      <DataQualityCard companyId={company.id} />

      <div className="card-grid">
        <div className="card">
          <div className="card-label">Ticker</div>
          <div className="card-value">{company.ticker}</div>
        </div>
        <div className="card">
          <div className="card-label">ISIN</div>
          <div className="card-value">{company.isin || '--'}</div>
        </div>
        <div className="card">
          <div className="card-label">Sector</div>
          <div className="card-value">{company.sector || '--'}</div>
        </div>
        <div className="card">
          <div className="card-label">Industry</div>
          <div className="card-value">{company.industry || '--'}</div>
        </div>
        <div className="card">
          <div className="card-label">Currency</div>
          <div className="card-value">{company.currency}</div>
        </div>
        <div className="card">
          <div className="card-label">Status</div>
          <div className={`card-value ${company.status === 'ACTIVE' ? 'positive' : 'negative'}`}>
            {company.status}
          </div>
        </div>
      </div>

      {latestPrice && (
        <div className="card-grid">
          <div className="card">
            <div className="card-label">Latest Close</div>
            <div className="card-value">{latestPrice.close}</div>
            <div className="card-subtitle">{latestPrice.date}</div>
          </div>
          <div className="card">
            <div className="card-label">Open</div>
            <div className="card-value">{latestPrice.open}</div>
          </div>
          <div className="card">
            <div className="card-label">High</div>
            <div className="card-value">{latestPrice.high}</div>
          </div>
          <div className="card">
            <div className="card-label">Low</div>
            <div className="card-value">{latestPrice.low}</div>
          </div>
          <div className="card">
            <div className="card-label">Volume</div>
            <div className="card-value">{latestPrice.volume.toLocaleString()}</div>
          </div>
        </div>
      )}

      <div>
        <h2 className="section-title">Historical Prices</h2>
        {loadingPrices && <div className="loading">Loading prices...</div>}
        {pricesData && pricesData.items.length > 0 && (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Open</th>
                  <th>High</th>
                  <th>Low</th>
                  <th>Close</th>
                  <th>Volume</th>
                </tr>
              </thead>
              <tbody>
                {pricesData.items.map((price) => (
                  <tr key={price.id}>
                    <td>{price.date}</td>
                    <td>{price.open}</td>
                    <td>{price.high}</td>
                    <td>{price.low}</td>
                    <td>{price.close}</td>
                    <td>{price.volume.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {pricesData && pricesData.items.length === 0 && (
          <div className="loading">No price data available</div>
        )}
      </div>
    </div>
  )
}

