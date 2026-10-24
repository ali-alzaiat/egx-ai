import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useCompanyByTicker, useCompanyPrices, useLatestPrice } from '../api/client'
import { formatAsOf, formatPrice, formatVolume } from '../lib/format'

/**
 * Hub Overview (interim). The hub layout route owns the header, tabs, company
 * validation and the data-quality card (now under Financials); "Refresh market
 * data" moved to Admin. The Overview rebuild comes with the hub-tabs lane.
 */
export default function CompanyDetail() {
  const { ticker } = useParams<{ ticker: string }>()
  const { data: company } = useCompanyByTicker(ticker)
  const { data: latestPrice, isLoading: loadingLatest } = useLatestPrice(company?.id)

  const oneYearAgo = new Date()
  oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1)
  const startDate = oneYearAgo.toISOString().split('T')[0]!

  const [pricePage, setPricePage] = useState(1)
  useEffect(() => {
    setPricePage(1)
  }, [ticker])

  const { data: pricesData, isLoading: loadingPrices } = useCompanyPrices(company?.id, {
    start_date: startDate,
    page_size: 50,
    page: pricePage,
  })

  if (!company) return null

  const prices = pricesData?.items ?? []
  const visiblePrices = prices.filter(
    (p) => !(p.open === p.high && p.high === p.low && p.low === p.close && p.volume === 0),
  )
  const hiddenCount = prices.length - visiblePrices.length

  return (
    <div className="page">
      <div className="card-grid">
        <div className="card">
          <div className="card-label">Latest Close</div>
          <div className="card-value">{formatPrice(latestPrice?.close)}</div>
          {latestPrice && (
            <div className="card-subtitle">As of {formatAsOf(latestPrice.date)} · end-of-day</div>
          )}
        </div>
        <div className="card">
          <div className="card-label">Open</div>
          <div className="card-value">{formatPrice(latestPrice?.open)}</div>
        </div>
        <div className="card">
          <div className="card-label">High</div>
          <div className="card-value">{formatPrice(latestPrice?.high)}</div>
        </div>
        <div className="card">
          <div className="card-label">Low</div>
          <div className="card-value">{formatPrice(latestPrice?.low)}</div>
        </div>
        <div className="card">
          <div className="card-label">Volume</div>
          <div className="card-value">
            {latestPrice ? formatVolume(latestPrice.volume) : '—'}
          </div>
        </div>
      </div>
      {!loadingLatest && !latestPrice && (
        <p className="muted">No price data from the configured source for {company.ticker}.</p>
      )}

      <div>
        <h2 className="section-title">Historical Prices</h2>
        {loadingPrices && <div className="loading">Loading prices...</div>}
        {!loadingPrices && visiblePrices.length > 0 && (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th className="num">Open</th>
                  <th className="num">High</th>
                  <th className="num">Low</th>
                  <th className="num">Close</th>
                  <th className="num">Volume</th>
                </tr>
              </thead>
              <tbody>
                {visiblePrices.map((price) => (
                  <tr key={price.id}>
                    <td>{price.date}</td>
                    <td className="num" dir="ltr">{formatPrice(price.open)}</td>
                    <td className="num" dir="ltr">{formatPrice(price.high)}</td>
                    <td className="num" dir="ltr">{formatPrice(price.low)}</td>
                    <td className="num" dir="ltr">{formatPrice(price.close)}</td>
                    <td className="num" dir="ltr">{formatVolume(price.volume)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loadingPrices && visiblePrices.length === 0 && (
          <div className="loading">No price data available</div>
        )}
        {hiddenCount > 0 && (
          <p className="muted">Non-trading days are hidden.</p>
        )}
        {pricesData && pricesData.total_pages > 1 && (
          <div className="pagination">
            <button
              onClick={() => setPricePage((p) => Math.max(1, p - 1))}
              disabled={pricePage === 1}
              className="pagination-btn"
            >
              Previous
            </button>
            <span className="pagination-info">
              Page {pricePage} of {pricesData.total_pages} ({pricesData.total} trading days)
            </span>
            <button
              onClick={() => setPricePage((p) => Math.min(pricesData.total_pages, p + 1))}
              disabled={pricePage === pricesData.total_pages}
              className="pagination-btn"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
