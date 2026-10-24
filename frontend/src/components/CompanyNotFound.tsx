import { Link } from "react-router-dom";
import { useLang } from "../i18n/useLang";
import { PageHeader } from "./ui/PageHeader";
import { PageTitle } from "./ui/PageTitle";

// Shared 404 state for every company view: echo the ticker the user typed and
// give two ways back.
export default function CompanyNotFound({ ticker }: { ticker?: string }) {
  const { t } = useLang();
  const title = t("company_not_found_title", { ticker: ticker ?? "" });
  return (
    <div className="page">
      <PageTitle parts={[t("company_not_found_title", { ticker: ticker ?? "" })]} />
      <PageHeader title={title} subtitle={t("company_not_found_body")} />
      <div className="company-actions">
        <Link to="/companies" className="btn btn-secondary">
          {t("company_browse")}
        </Link>
        <Link
          to={`/companies?search=${encodeURIComponent(ticker ?? "")}`}
          className="btn btn-secondary"
        >
          {t("company_search_another")}
        </Link>
      </div>
    </div>
  );
}
