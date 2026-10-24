import { useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";
import { useLang } from "../../i18n/useLang";
import { HUB_TABS, activeTab, relativePath } from "./tabs";

/**
 * Sticky route-link strip (spec 1.4). On narrow screens it scrolls
 * horizontally with no wrapping, and the active tab is scrolled into view
 * whenever it changes.
 */
export default function HubTabs({ base }: { base: string }) {
  const { pathname } = useLocation();
  const { t } = useLang();
  const current = activeTab(HUB_TABS, relativePath(pathname, base));
  const activeRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ inline: "center", block: "nearest" });
  }, [current?.path]);

  return (
    <nav className="tab-strip" aria-label={t("company_sections_aria")}>
      {HUB_TABS.map((tab) => {
        const active = current?.path === tab.path;
        return (
          <Link
            key={tab.path}
            ref={active ? activeRef : undefined}
            to={`${base}${tab.path}`}
            className="tab-link"
            aria-current={active ? "page" : undefined}
          >
            {t(tab.key)}
          </Link>
        );
      })}
    </nav>
  );
}
