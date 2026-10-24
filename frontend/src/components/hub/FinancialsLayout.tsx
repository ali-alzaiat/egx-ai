import { Link, Outlet, useLocation, useParams } from "react-router-dom";
import { useLang } from "../../i18n/useLang";
import { FINANCIALS_SECTIONS, isSectionActive, relativePath } from "./tabs";

/** Financials tab: one tab, four sections (statements, ratios, metrics, data quality). */
export default function FinancialsLayout() {
  const { ticker = "" } = useParams<{ ticker: string }>();
  const { pathname } = useLocation();
  const { t } = useLang();
  const base = `/companies/${encodeURIComponent(ticker)}/financials`;
  const rel = relativePath(pathname, base) ?? "";

  return (
    <div>
      <nav className="subnav" aria-label={t("financials_sections_aria")}>
        {FINANCIALS_SECTIONS.map((section) => {
          const active = isSectionActive(section, rel);
          return (
            <Link
              key={section.path}
              to={`${base}${section.path}`}
              className="tab-link"
              aria-current={active ? "page" : undefined}
            >
              {t(section.key)}
            </Link>
          );
        })}
      </nav>
      <Outlet />
    </div>
  );
}
