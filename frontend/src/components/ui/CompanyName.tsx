import { useLang } from "../../i18n/useLang";

/**
 * Company name for the current language. In Arabic, `name_ar` is used when it
 * exists; otherwise the Latin name is isolated in `<bdi dir="ltr" lang="en">`
 * so punctuation and truncation behave (spec 6.5).
 */
export function CompanyName({ name, nameAr }: { name: string; nameAr?: string | null }) {
  const { lang } = useLang();
  if (lang !== "ar") return <>{name}</>;
  if (nameAr) return <span lang="ar">{nameAr}</span>;
  return (
    <bdi dir="ltr" lang="en">
      {name}
    </bdi>
  );
}

/** Plain-text variant for attributes and document titles. */
export function companyNameText(lang: "en" | "ar", name: string, nameAr?: string | null): string {
  return lang === "ar" && nameAr ? nameAr : name;
}
