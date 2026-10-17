import { Outlet, Link, useLocation } from "react-router-dom";
import { useLang } from "../i18n/useLang";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/companies", label: "Companies" },
  { to: "/rankings", label: "Market Rankings" },
  { to: "/screening", label: "Screening" },
  { to: "/pricing", label: "Pricing" },
  { to: "/watchlists", label: "Watchlists" },
  { to: "/alerts", label: "Alerts" },
  { to: "/events", label: "Events" },
];

function isActive(itemTo: string, pathname: string): boolean {
  if (itemTo === "/") return pathname === "/";
  return pathname === itemTo || pathname.startsWith(`${itemTo}/`);
}

export default function Layout() {
  const location = useLocation();
  const { lang, setLang } = useLang();

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">EGX AI</div>
        <button
          type="button"
          onClick={() => setLang(lang === "en" ? "ar" : "en")}
          className="lang-toggle"
        >
          {lang === "en" ? "AR" : "EN"}
        </button>
        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const active = isActive(item.to, location.pathname);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`sidebar-link ${active ? "active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
