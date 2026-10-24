import { Link, useSearchParams } from "react-router-dom";
import { useCompanyByTicker } from "../../api/client";
import CompanySearch from "../../components/ui/CompanySearch";
import { EmptyState } from "../../components/ui/States";
import { useLang } from "../../i18n/useLang";

/**
 * Per-company admin section (disclosures, peers, thesis): starts with a
 * CompanyPicker; the picked ticker lives in `?ticker=` and the section content
 * renders only after a pick (spec 1.5). The write forms still live on the
 * company page and move here in the per-page lanes.
 */
export default function AdminCompanySection() {
  const { t } = useLang();
  const [params, setParams] = useSearchParams();
  const ticker = params.get("ticker") ?? undefined;
  const { data: company } = useCompanyByTicker(ticker);

  return (
    <section className="page">
      <div className="admin-picker">
        <CompanySearch
          mode="picker"
          value={company ?? null}
          onSelect={(c) => setParams({ ticker: c.ticker }, { replace: true })}
          onClear={() => setParams({}, { replace: true })}
        />
      </div>
      {!company ? (
        <EmptyState>{t("admin_pick_company")}</EmptyState>
      ) : (
        <>
          <EmptyState>{t("admin_section_pending")}</EmptyState>
          <div className="company-actions">
            <Link to={`/companies/${encodeURIComponent(company.ticker)}`} className="btn btn-secondary">
              {t("admin_open_company")}
            </Link>
          </div>
        </>
      )}
    </section>
  );
}
