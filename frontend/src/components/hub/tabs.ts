import type { CopyKey } from "../../i18n";

export interface HubTab {
  /** Path relative to /companies/:ticker. "" is the Overview. */
  path: string;
  key: CopyKey;
}

/** The seven hub tabs (spec 1.4). Tabs are route links, not an ARIA tablist. */
export const HUB_TABS: readonly HubTab[] = [
  { path: "", key: "tab_overview" },
  { path: "/price", key: "tab_price" },
  { path: "/financials", key: "tab_financials" },
  { path: "/valuation", key: "tab_valuation" },
  { path: "/shariah", key: "tab_shariah" },
  { path: "/peers", key: "tab_peers" },
  { path: "/thesis", key: "tab_thesis" },
];

/** Sub-sections of the Financials tab. */
export const FINANCIALS_SECTIONS: readonly HubTab[] = [
  { path: "", key: "tab_statements" },
  { path: "/ratios", key: "tab_ratios" },
  { path: "/metrics", key: "tab_metrics" },
  { path: "/quality", key: "tab_quality" },
];

/** Path below `base` with any trailing slash removed ("" for the base itself). */
export function relativePath(pathname: string, base: string): string | null {
  const clean = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  if (clean === base) return "";
  return clean.startsWith(`${base}/`) ? clean.slice(base.length) : null;
}

/** The tab whose route contains `rel`; null for paths the hub does not know (falls to Not found). */
export function activeTab(tabs: readonly HubTab[], rel: string | null): HubTab | null {
  if (rel === null) return null;
  if (rel === "") return tabs.find((t) => t.path === "") ?? null;
  return tabs.find((t) => t.path !== "" && (rel === t.path || rel.startsWith(`${t.path}/`))) ?? null;
}

/** Sub-section active state: the base section only matches exactly, others by prefix. */
export function isSectionActive(section: HubTab, rel: string): boolean {
  return section.path === "" ? rel === "" : rel === section.path || rel.startsWith(`${section.path}/`);
}
