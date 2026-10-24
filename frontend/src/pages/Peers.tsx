import { useParams } from 'react-router-dom'
import { useCompanyByTicker } from '../api/client'
import CompanyNotFound from '../components/CompanyNotFound'
import PeersTab from '../components/PeersTab'

export default function Peers() {
  const { ticker } = useParams<{ ticker: string }>()
  const { data: company, isLoading, error } = useCompanyByTicker(ticker)

  if (isLoading) {
    return <div className="loading">Loading company...</div>
  }

  if (error || !company) {
    return <CompanyNotFound ticker={ticker} />
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Peers - {company.ticker}</h2>
          <p className="subtitle">{company.name}</p>
        </div>
      </div>


      <PeersTab companyId={company.id} ticker={company.ticker} />
    </div>
  )
}
