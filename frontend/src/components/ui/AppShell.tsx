import { Suspense, useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useLang } from "../../i18n/useLang";
import type { CopyKey } from "../../i18n";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { useTheme, type Theme } from "../../theme/useTheme";
import CompanySearch from "./CompanySearch";
import { CloseIcon, MenuIcon, SearchIcon } from "./icons";
import { PageTitle } from "./PageTitle";
import { Segmented } from "./Segmented";
import { LoadingState } from "./States";

interface NavItem {
  to: string;
  key: CopyKey;
}

const NAV_GROUPS: readonly { label: CopyKey; items: readonly NavItem[] }[] = [
  {
    label: "nav_group_markets",
    items: [
      { to: "/", key: "nav_dashboard" },
      { to: "/recommendations", key: "nav_recommendations" },
      { to: "/rankings", key: "nav_rankings" },
    ],
  },
  {
    label: "nav_group_research",
    items: [
      { to: "/companies", key: "nav_companies" },
      { to: "/screening", key: "nav_screening" },
    ],
  },
  {
    label: "nav_group_tracking",
    items: [
      { to: "/watchlists", key: "nav_watchlists" },
      { to: "/alerts", key: "nav_alerts" },
      { to: "/events", key: "nav_events" },
    ],
  },
];

const ADMIN_ITEM: NavItem = { to: "/admin", key: "nav_admin" };

/** Hub routes keep "Companies" active because they sit under /companies/. */
export function isActivePath(itemTo: string, pathname: string): boolean {
  if (itemTo === "/") return pathname === "/";
  return pathname === itemTo || pathname.startsWith(`${itemTo}/`);
}

/** Nav key naming the page for the document title; hub, admin sections and unknown paths render their own. */
export function routeTitleKey(pathname: string): CopyKey | null {
  if (/^\/companies\/[^/]+/.test(pathname)) return null;
  if (pathname.startsWith("/admin")) return null;
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      if (isActivePath(item.to, pathname)) return item.key;
    }
  }
  return null;
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

function NavGroups() {
  const { pathname } = useLocation();
  const { t } = useLang();
  return (
    <nav className="nav-groups" aria-label={t("sidebar_aria")}>
      {NAV_GROUPS.map((group) => (
        <div key={group.label} role="group" aria-label={t(group.label)}>
          <div className="nav-group-label" aria-hidden="true">
            {t(group.label)}
          </div>
          {group.items.map((item) => {
            const active = isActivePath(item.to, pathname);
            return (
              <Link
                key={item.to}
                to={item.to}
                className="nav-item"
                aria-current={active ? "page" : undefined}
              >
                {t(item.key)}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

function SidebarFooter() {
  const { pathname } = useLocation();
  const { lang, setLang, t } = useLang();
  const { theme, setTheme } = useTheme();
  const themeOptions: { value: Theme; label: string }[] = [
    { value: "system", label: t("theme_system") },
    { value: "light", label: t("theme_light") },
    { value: "dark", label: t("theme_dark") },
  ];
  return (
    <div className="sidebar-footer">
      <Segmented
        label={t("lang_toggle_aria")}
        value={lang}
        onChange={setLang}
        options={[
          { value: "en", label: "English", lang: "en" },
          { value: "ar", label: "عربي", lang: "ar" },
        ]}
      />
      <Segmented label={t("theme_aria")} value={theme} onChange={setTheme} options={themeOptions} />
      <Link
        to={ADMIN_ITEM.to}
        className="sidebar-admin"
        aria-current={isActivePath(ADMIN_ITEM.to, pathname) ? "page" : undefined}
      >
        {t(ADMIN_ITEM.key)}
      </Link>
    </div>
  );
}

/** Drawer with focus trap, Esc, scrim click and body scroll lock (spec 1.3). */
function Drawer({ onClose }: { onClose: () => void }) {
  const { t } = useLang();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.body.classList.add("scroll-locked");
    ref.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    return () => document.body.classList.remove("scroll-locked");
  }, []);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>): void => {
    if (e.key === "Escape") {
      e.stopPropagation();
      onClose();
      return;
    }
    if (e.key !== "Tab") return;
    const nodes = ref.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
    const first = nodes?.[0];
    const last = nodes?.[nodes.length - 1];
    if (!first || !last) return;
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  return (
    <>
      <div className="scrim" onClick={onClose} aria-hidden="true" />
      <div
        ref={ref}
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label={t("sidebar_aria")}
        onKeyDown={onKeyDown}
      >
        <div className="drawer-head">
          <Link to="/" className="wordmark">
            EGX AI
          </Link>
          <button type="button" className="icon-btn" aria-label={t("menu_close")} onClick={onClose}>
            <CloseIcon />
          </button>
        </div>
        <NavGroups />
        <SidebarFooter />
      </div>
    </>
  );
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable;
}

export default function AppShell() {
  const { pathname } = useLocation();
  const { t } = useLang();
  const desktop = useMediaQuery("(min-width: 1024px)");
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const searchButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setMenuOpen(false);
    setSearchOpen(false);
  }, [pathname]);

  // "/" and Ctrl/Cmd+K focus the search unless typing in a field (spec 3.3).
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent): void => {
      if (isTypingTarget(e.target)) return;
      const slash = e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey;
      const ctrlK = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k";
      if (!slash && !ctrlK) return;
      e.preventDefault();
      if (desktop) searchRef.current?.focus();
      else setSearchOpen(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [desktop]);

  const closeMenu = useCallback((): void => {
    setMenuOpen(false);
    menuButtonRef.current?.focus();
  }, []);

  const closeSearch = useCallback((): void => {
    setSearchOpen(false);
    searchButtonRef.current?.focus();
  }, []);

  const titleKey = routeTitleKey(pathname);

  return (
    <div className="layout">
      {titleKey && <PageTitle parts={[t(titleKey)]} />}
      <a href="#main" className="skip-link">
        {t("skip_to_content")}
      </a>

      <aside className="sidebar">
        <Link to="/" className="wordmark">
          EGX AI
        </Link>
        <CompanySearch mode="search" inputRef={searchRef} />
        <NavGroups />
        <SidebarFooter />
      </aside>

      <header className="topbar">
        <button
          ref={menuButtonRef}
          type="button"
          className="icon-btn"
          aria-label={t("menu_open")}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen(true)}
        >
          <MenuIcon />
        </button>
        <Link to="/" className="wordmark">
          EGX AI
        </Link>
        <button
          ref={searchButtonRef}
          type="button"
          className="icon-btn"
          aria-label={t("search_open")}
          aria-expanded={searchOpen}
          onClick={() => setSearchOpen((v) => !v)}
        >
          <SearchIcon />
        </button>
      </header>
      {searchOpen && (
        <div className="search-overlay">
          <CompanySearch mode="search" autoFocus onDone={closeSearch} />
        </div>
      )}
      {menuOpen && <Drawer onClose={closeMenu} />}

      <main id="main" className="main-content">
        <Suspense fallback={<LoadingState />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}
