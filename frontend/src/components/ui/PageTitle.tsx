import { useLang } from "../../i18n/useLang";

/** Sets the document title as "{parts} · EGX AI" through React 19 `<title>` hoisting. */
export function PageTitle({ parts }: { parts: readonly string[] }) {
  const { t } = useLang();
  const text = [...parts.filter((p) => p.trim() !== ""), t("title_suffix")].join(" · ");
  return <title>{text}</title>;
}
