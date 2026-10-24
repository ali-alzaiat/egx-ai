import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import { Notice } from "../../components/ui/Notice";
import { PageHeader } from "../../components/ui/PageHeader";
import { PageTitle } from "../../components/ui/PageTitle";
import { useLang } from "../../i18n/useLang";
import type { CopyKey } from "../../i18n";

const SECTIONS: readonly { path: string; key: CopyKey }[] = [
  { path: "market", key: "admin_market" },
  { path: "intake", key: "nav_intake" },
  { path: "disclosures", key: "admin_disclosures" },
  { path: "peers", key: "admin_peers" },
  { path: "thesis", key: "admin_thesis" },
];

/** `/admin` shell (spec 1.5): header, write-warning notice, route-based sub-navigation. */
export default function AdminLayout() {
  const { pathname } = useLocation();
  const { t } = useLang();
  const segment = pathname.replace(/\/+$/, "").split("/")[2] ?? "";
  const section = SECTIONS.find((s) => s.path === segment);

  if (pathname.replace(/\/+$/, "") === "/admin") return <Navigate to="/admin/market" replace />;

  return (
    <div className="page">
      <PageTitle parts={section ? [t(section.key), t("admin_title")] : [t("admin_title")]} />
      <PageHeader title={t("admin_title")} />
      <Notice variant="warning">{t("admin_notice")}</Notice>
      <nav className="tab-strip" aria-label={t("admin_sections_aria")}>
        {SECTIONS.map((s) => (
          <Link
            key={s.path}
            to={`/admin/${s.path}`}
            className="tab-link"
            aria-current={s.path === segment ? "page" : undefined}
          >
            {t(s.key)}
          </Link>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
