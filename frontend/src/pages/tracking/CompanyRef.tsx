import { Link } from "react-router-dom";
import { CompanyName } from "../../components/ui/CompanyName";
import { useLang } from "../../i18n/useLang";
import type { Company } from "../../types";

/** "TICKER  Name" linking to the company hub; an unresolved id reads "Unknown company", never an id. */
export function CompanyRef({ company, loading = false }: { company: Company | undefined; loading?: boolean }) {
  const { t } = useLang();
  if (!company && loading) return <span className="text-note">{t("loading")}</span>;
  if (!company) return <span className="text-note">{t("trk_unknown_company")}</span>;
  return (
    <span className="trk-company">
      <Link to={`/companies/${encodeURIComponent(company.ticker)}`} dir="ltr">
        {company.ticker}
      </Link>
      <span className="text-note">
        <CompanyName name={company.name} nameAr={company.name_ar} />
      </span>
    </span>
  );
}
