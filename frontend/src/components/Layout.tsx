import { Outlet, Link, useLocation } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/companies', label: 'Companies' },
  { to: '/screener', label: 'Screener' },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/research', label: 'Research' },
  { to: '/alerts', label: 'Alerts' },
]

export default function Layout() {
  const location = useLocation()

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">EGX AI</div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`sidebar-link ${location.pathname === item.to ? 'active' : ''}`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
