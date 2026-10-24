import { Link } from "react-router-dom";
import { PageHeader } from "../components/ui/PageHeader";
import { PageTitle } from "../components/ui/PageTitle";
import { useLang } from "../i18n/useLang";

/**
 * Unknown route, including the removed /companies/:ticker/ai (R43 AC-8).
 * `nested` is for layouts that already render the page's h1 (company hub, admin).
 */
export default function NotFound({ nested = false }: { nested?: boolean }) {
  const { t } = useLang();
  return (
    <div className="page">
      <PageTitle parts={[t("not_found_title")]} />
      {nested ? (
        <div className="page-header">
          <div>
            <h2>{t("not_found_title")}</h2>
            <p>{t("not_found_body")}</p>
          </div>
        </div>
      ) : (
        <PageHeader title={t("not_found_title")} subtitle={t("not_found_body")} />
      )}
      <div className="company-actions">
        <Link to="/" className="btn btn-secondary">
          {t("not_found_home")}
        </Link>
      </div>
    </div>
  );
}
