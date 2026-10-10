import { Outlet, Link, useLocation } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/companies', label: 'Companies' },
  { to: '/rankings', label: 'Market Rankings' },
  { to: '/screening', label: 'Screening' },
]

function isActive(itemTo: string, pathname: string): boolean {
  if (itemTo === '/') return pathname === '/'
  // Prefix match so /companies/COMI/financials still highlights Companies.
  return pathname === itemTo || pathname.startsWith(`${itemTo}/`)
}

export default function Layout() {
  const location = useLocation()

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">EGX AI</div>
        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const active = isActive(item.to, location.pathname)
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`sidebar-link ${active ? 'active' : ''}`}
                aria-current={active ? 'page' : undefined}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
