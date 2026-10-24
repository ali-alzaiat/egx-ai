import type { ReactNode } from "react";
import { useLang } from "../../i18n/useLang";

/**
 * Backend free text is English until the localizable-reasons work lands (spec
 * 6.11): in Arabic it is isolated in an LTR English span so it neither reorders
 * nor drags punctuation across the line.
 */
export function ForeignText({ children }: { children: ReactNode }) {
  const { lang } = useLang();
  if (lang !== "ar") return <>{children}</>;
  return (
    <span lang="en" dir="ltr">
      {children}
    </span>
  );
}
