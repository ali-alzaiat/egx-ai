import { Suspense } from "react";
import { Outlet, useLocation, useParams } from "react-router-dom";
import { useCompanyByTicker } from "../../api/client";
import { useLang } from "../../i18n/useLang";
import CompanyNotFound from "../CompanyNotFound";
import { companyNameText } from "../ui/CompanyName";
import { ErrorState, LoadingState } from "../ui/States";
import { PageTitle } from "../ui/PageTitle";
import CompanyHeader from "./CompanyHeader";
import HubTabs from "./HubTabs";
import { HUB_TABS, activeTab, relativePath } from "./tabs";

/**
 * Hub layout route (`/companies/:ticker`): validates the company once, renders
 * the single CompanyHeader and the tab strip, and mounts the tab through the
 * Outlet. Tab pages no longer render their own title or tabs.
 */
export default function CompanyHub() {
  const { ticker = "" } = useParams<{ ticker: string }>();
  const { pathname } = useLocation();
  const { t, lang } = useLang();
  const { data: company, isLoading, error, refetch } = useCompanyByTicker(ticker);

  if (isLoading) return <LoadingState thing={t("loading_company")} />;
  if (error && !error.message.includes("404")) {
    return <ErrorState thing={t("loading_company")} onRetry={() => void refetch()} />;
  }
  if (!company) return <CompanyNotFound ticker={ticker} />;

  const base = `/companies/${encodeURIComponent(ticker)}`;
  const tab = activeTab(HUB_TABS, relativePath(pathname, base));

  return (
    <div className="hub">
      {/* An unknown tab falls through to Not found, which sets its own title. */}
      {tab && (
        <PageTitle
          parts={[`${company.ticker} ${companyNameText(lang, company.name, company.name_ar)}`, t(tab.key)]}
        />
      )}
      <CompanyHeader company={company} />
      <HubTabs base={base} />
      <Suspense fallback={<LoadingState />}>
        <Outlet />
      </Suspense>
    </div>
  );
}
