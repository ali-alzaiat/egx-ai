import { Link } from "react-router-dom";
import { Button } from "@/components/shadcn/button";
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
        <Button asChild variant="outline">
          <Link to="/companies">{t("company_browse")}</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to={`/companies?search=${encodeURIComponent(ticker ?? "")}`}>{t("company_search_another")}</Link>
        </Button>
      </div>
    </div>
  );
}
