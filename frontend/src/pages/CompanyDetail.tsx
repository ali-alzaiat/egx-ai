import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  startMarketRefresh,
  useCompanyByTicker,
  useCompanyPrices,
  useLatestPrice,
  useSyncStatus,
} from '../api/client'
import { formatAsOf, formatPrice, formatVolume } from '../lib/format'
import CompanyNotFound from '../components/CompanyNotFound'
import CompanyTabs from '../components/CompanyTabs'
import DataQualityCard from '../components/DataQualityCard'
import type { SyncJobStatus } from '../types'

const REFRESH_KEYS = [
  ['dataQuality'],
  ['signals'],
  ['prices'],
  ['latestPrice'],
  ['dataSources'],
] as const

function liveStatusLine(job: SyncJobStatus | undefined): string {
  if (!job || job.status === 'idle') return 'Refreshing…'
  if (job.status === 'accepted') return 'Refreshing…'
  switch (job.phase) {
    case 'universe':
      return 'Refreshing company list…'
    case 'prices':
      return job.progress
        ? `Fetching prices ${job.progress.completed}/${job.progress.total}…`
        : 'Fetching prices…'
    case 'assessment':
      return 'Scoring data quality…'
    default:
      return 'Refreshing…'
  }
}

export default function CompanyDetail() {
  const { ticker } = useParams<{ ticker: string }>()
  const queryClient = useQueryClient()
  const { data: company, isLoading: loadingCompany, error: errorCompany } = useCompanyByTicker(ticker)

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

  // ─── Market refresh (R16, runSignals pattern) ───
  const [refreshing, setRefreshing] = useState(false)
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null)
  const [refreshErr, setRefreshErr] = useState<string | null>(null)
  const syncQuery = useSyncStatus()
  const syncJob = syncQuery.data

  useEffect(() => {
    if (!refreshing) return
    const status = syncJob?.status
    if (status !== 'done' && status !== 'partial' && status !== 'failed') return
    for (const key of REFRESH_KEYS) {
      void queryClient.invalidateQueries({ queryKey: [...key] })
    }
    if (status === 'failed') {
      setRefreshErr(`Refresh failed: ${syncJob?.error ?? 'unknown error'}`)
    } else {
      const records = syncJob?.prices?.records_written ?? 0
      const scores = syncJob?.assessment?.scores_written ?? 0
      let msg = `Refresh complete — ${records} price records, ${scores} quality scores.`
      if (status === 'partial') {
        msg += ` Some tickers failed (${syncJob?.prices?.failed_count ?? 0}) — details in the browser console.`
        console.warn('Market refresh partial failure:', syncJob?.prices?.failed_tickers)
      }
      setRefreshMsg(msg)
      window.setTimeout(() => setRefreshMsg(null), 4000)
    }
    setRefreshing(false)
  }, [refreshing, syncJob, queryClient])

  const handleRefresh = async (): Promise<void> => {
    setRefreshing(true)
    setRefreshErr(null)
    setRefreshMsg(null)
    try {
      // 409 adopts the live job instead of throwing — poll it either way.
      await startMarketRefresh()
      await syncQuery.refetch()
    } catch (err) {
      setRefreshing(false)
      setRefreshErr(`Refresh failed: ${err instanceof Error ? err.message : 'unknown error'}`)
    }
  }

  if (loadingCompany) return <div className="loading">Loading company...</div>
  if (errorCompany || !company) return <CompanyNotFound ticker={ticker} />

  const prices = pricesData?.items ?? []
  const visiblePrices = prices.filter(
    (p) => !(p.open === p.high && p.high === p.low && p.low === p.close && p.volume === 0),
  )
  const hiddenCount = prices.length - visiblePrices.length

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>{company.ticker} — {company.name}</h1>
          {company.name_ar && <p className="subtitle">{company.name_ar}</p>}
        </div>
        <div>
          <button className="btn btn-secondary" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? 'Refreshing…' : 'Refresh market data'}
          </button>
          {refreshing && (
            <p role="status" className="muted">{liveStatusLine(syncJob)}</p>
          )}
          {refreshMsg && (
            <p role="status" className="muted">{refreshMsg}</p>
          )}
        </div>
      </div>
      {refreshErr && <div className="alert alert-error">{refreshErr}</div>}

      <CompanyTabs ticker={company.ticker} />

      <DataQualityCard companyId={company.id} />

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
                  <th>Open</th>
                  <th>High</th>
                  <th>Low</th>
                  <th>Close</th>
                  <th>Volume</th>
                </tr>
              </thead>
              <tbody>
                {visiblePrices.map((price) => (
                  <tr key={price.id}>
                    <td>{price.date}</td>
                    <td>{formatPrice(price.open)}</td>
                    <td>{formatPrice(price.high)}</td>
                    <td>{formatPrice(price.low)}</td>
                    <td>{formatPrice(price.close)}</td>
                    <td>{formatVolume(price.volume)}</td>
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
