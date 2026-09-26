/**
 * Shown by the pages that require real financial statements.
 *
 * Financial metrics, valuation and Shariah screening all need audited figures
 * from official EGX / FRA / company disclosures. None have been ingested yet, and
 * fabricating them would be worse than showing nothing, so these pages explain
 * the gap instead of rendering empty or misleading results.
 */
export default function PendingFinancialData({
  feature,
  ticker,
}: {
  feature: string
  ticker?: string
}) {
  return (
    <div className="page">
      <div className="page-header">
        <h1>{feature}</h1>
        {ticker && <p className="subtitle">{ticker}</p>}
      </div>

      <div className="pending-panel">
        <div className="pending-badge">Awaiting official disclosures</div>

        <h2>This feature has no real data yet</h2>

        <p>
          {feature} is calculated from financial statements. The app ingests those from
          official sources — Egyptian Exchange and FRA filings, and company investor
          relations disclosures — and that ingestion layer is not built yet.
        </p>

        <p>
          Rather than show invented numbers, the feature is disabled. Nothing on this
          page is estimated, interpolated or filled in with placeholder values.
        </p>

        <h3>What works today</h3>
        <ul>
          <li>
            <strong>Market Rankings</strong> — every listed company scored on price
            momentum, trend, risk and liquidity, relative to the rest of the market.
          </li>
          <li>
            <strong>Technical Analysis</strong> — indicators computed from real daily
            prices.
          </li>
        </ul>

        <h3>Why it is not faked</h3>
        <p>
          A valuation or Shariah verdict built on synthetic fundamentals would look
          authoritative and be worthless — worse than no answer, because it invites a
          decision. When real filings are ingested, these pages will activate
          automatically.
        </p>
      </div>
    </div>
  )
}
