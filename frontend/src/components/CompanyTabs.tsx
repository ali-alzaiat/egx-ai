import { Link, useLocation } from "react-router-dom";
import { useLang } from "../i18n/useLang";
import type { CopyKey } from "../i18n";

const TABS: { path: string; key: CopyKey }[] = [
  { path: "", key: "tab_overview" },
  { path: "/signals", key: "tab_signals" },
  { path: "/financials", key: "tab_financials" },
  { path: "/statements", key: "tab_statements" },
  { path: "/ratios", key: "tab_ratios" },
  { path: "/metrics", key: "tab_metrics" },
  { path: "/technical", key: "tab_technical" },
  { path: "/valuation", key: "tab_valuation" },
  { path: "/score", key: "tab_score" },
  { path: "/screening", key: "tab_screening" },
  { path: "/peers", key: "tab_peers" },
  { path: "/thesis", key: "tab_thesis" },
  { path: "/disclosures", key: "tab_disclosures" },
];

export default function CompanyTabs({ ticker }: { ticker: string }) {
  const { pathname } = useLocation();
  const { t } = useLang();
  const base = `/companies/${ticker}`;

  return (
    <nav className="company-tabs" aria-label={t("company_sections_aria")}>
      {TABS.map((tab) => {
        const to = `${base}${tab.path}`;
        const active = pathname === to;
        return (
          <Link
            key={tab.path}
            to={to}
            className={`company-tab${active ? " active" : ""}`}
            aria-current={active ? "page" : undefined}
          >
            {t(tab.key)}
          </Link>
        );
      })}
    </nav>
  );
}
