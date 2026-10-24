import "../shared/fields.css";
import "./Admin.css";

import { Link, useLocation, useSearchParams } from "react-router-dom";
import { useCompanyByTicker } from "../../api/client";
import CompanySearch from "../../components/ui/CompanySearch";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States";
import { useLang } from "../../i18n/useLang";
import { FieldGroup } from "../shared/Field";
import AdminDisclosures from "./AdminDisclosures";
import AdminPeers from "./AdminPeers";
import AdminThesis from "./AdminThesis";

/**
 * Per-company admin section (disclosures, peers, thesis): starts with a
 * CompanyPicker; the picked ticker lives in `?ticker=` and the section content
 * renders only after a pick (spec 1.5). One component serves the three routes;
 * the path segment decides which section shows.
 */
export default function AdminCompanySection() {
  const { t } = useLang();
  const { pathname } = useLocation();
  const [params, setParams] = useSearchParams();
  const ticker = params.get("ticker") ?? undefined;
  const section = pathname.replace(/\/+$/, "").split("/")[2] ?? "";
  const company = useCompanyByTicker(ticker);

  let body;
  if (!ticker) {
    body = <EmptyState>{t("admin_pick_company")}</EmptyState>;
  } else if (company.isLoading) {
    body = <LoadingState thing={t("adm_things_company")} />;
  } else if (company.isError || !company.data) {
    body = <ErrorState thing={t("adm_things_company")} onRetry={() => void company.refetch()} />;
  } else if (section === "disclosures") {
    body = <AdminDisclosures key={company.data.id} company={company.data} />;
  } else if (section === "peers") {
    body = <AdminPeers key={company.data.id} company={company.data} />;
  } else {
    body = <AdminThesis key={company.data.id} company={company.data} />;
  }

  return (
    <section className="page">
      <div className="admin-picker">
        <FieldGroup label={t("adm_company")}>
          <CompanySearch
            mode="picker"
            value={company.data ?? null}
            onSelect={(c) => setParams({ ticker: c.ticker }, { replace: true })}
            onClear={() => setParams({}, { replace: true })}
          />
        </FieldGroup>
      </div>
      {body}
      {company.data && (
        <div>
          <Link to={`/companies/${encodeURIComponent(company.data.ticker)}`} className="btn btn-secondary">
            {t("admin_open_company")}
          </Link>
        </div>
      )}
    </section>
  );
}
