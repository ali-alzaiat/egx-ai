import { Outlet } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/screener', label: 'Screener' },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/research', label: 'Research' },
  { to: '/alerts', label: 'Alerts' },
]

export default function Layout() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">EGX AI</div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <a key={item.to} href={item.to} className="sidebar-link">
              {item.label}
            </a>
          ))}
        </nav>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
