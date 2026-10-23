import { Outlet, Link, useLocation } from "react-router-dom";
import { useLang } from "../i18n/useLang";
import type { CopyKey } from "../i18n";

const navItems: { to: string; key: CopyKey }[] = [
  { to: "/", key: "nav_dashboard" },
  { to: "/companies", key: "nav_companies" },
  { to: "/rankings", key: "nav_rankings" },
  { to: "/screening", key: "nav_screening" },
  { to: "/watchlists", key: "nav_watchlists" },
  { to: "/alerts", key: "nav_alerts" },
  { to: "/events", key: "nav_events" },
];

function isActive(itemTo: string, pathname: string): boolean {
  if (itemTo === "/") return pathname === "/";
  return pathname === itemTo || pathname.startsWith(`${itemTo}/`);
}

export default function Layout() {
  const location = useLocation();
  const { lang, setLang, t } = useLang();

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">EGX·AI</div>
        <nav className="sidebar-nav" aria-label={t("sidebar_aria")}>
          {navItems.map((item) => {
            const active = isActive(item.to, location.pathname);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`sidebar-link ${active ? "active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                {t(item.key)}
              </Link>
            );
          })}
        </nav>
        <button
          type="button"
          onClick={() => setLang(lang === "en" ? "ar" : "en")}
          lang={lang === "en" ? "ar" : "en"}
          className="lang-toggle sidebar-lang"
          aria-label={t("lang_toggle_aria")}
        >
          <span className={lang === "en" ? "on" : ""}>EN</span>
          <span aria-hidden>·</span>
          <span className={lang === "ar" ? "on" : ""}>ع</span>
        </button>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
