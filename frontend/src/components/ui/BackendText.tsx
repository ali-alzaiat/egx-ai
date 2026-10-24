import { useLang } from "../../i18n/useLang";

/**
 * Backend free text that is not localized yet (reasons, limitations, check
 * descriptions). In Arabic it is isolated as English so punctuation and
 * direction do not break the surrounding sentence (spec 6.11).
 */
export function BackendText({ children }: { children: string }) {
  const { lang } = useLang();
  return lang === "ar" ? (
    <span lang="en" dir="ltr">
      {children}
    </span>
  ) : (
    <>{children}</>
  );
}
