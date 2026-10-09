import { Link, useLocation } from 'react-router-dom'

// The 7 company views, in reading order (F2/F3: one shared tab row everywhere).
const TABS = [
  { path: '', label: 'Overview' },
  { path: '/financials', label: 'Financial Data' },
  { path: '/metrics', label: 'Metrics' },
  { path: '/technical', label: 'Technical' },
  { path: '/ai', label: 'AI Insights' },
  { path: '/screening', label: 'Shariah Screening' },
  { path: '/valuation', label: 'Valuation' },
]

export default function CompanyTabs({ ticker }: { ticker: string }) {
  const { pathname } = useLocation()
  const base = `/companies/${ticker}`

  return (
    <nav className="company-tabs" aria-label="Company sections">
      {TABS.map((tab) => {
        const to = `${base}${tab.path}`
        const active = pathname === to
        return (
          <Link
            key={tab.path}
            to={to}
            className={`company-tab${active ? ' active' : ''}`}
            aria-current={active ? 'page' : undefined}
          >
            {tab.label}
          </Link>
        )
      })}
    </nav>
  )
}