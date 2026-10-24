import { useLang } from "../../i18n/useLang";

type Translate = ReturnType<typeof useLang>["t"];

/**
 * Localized text for a missing-value reason. `missing:<line>` is mapped to
 * "Missing line: {line}"; other free text passes through (it waits for backend B5).
 */
export function missingReasonText(
  reason: string | null | undefined,
  t: Translate,
  lineLabel?: (line: string) => string,
): string {
  if (!reason) return t("missing_default");
  const match = /^missing:(.+)$/.exec(reason);
  const line = match?.[1];
  if (line) return t("missing_line", { line: lineLabel ? lineLabel(line) : line.replace(/_/g, " ") });
  return reason;
}

/**
 * A missing value: "—" with the localized reason as tooltip and for screen
 * readers. Never "0", blank, "NaN" or "MISSING" (spec 3.6).
 */
export function Missing({
  reason,
  localized,
  lineLabel,
}: {
  /** Backend reason code or free text. */
  reason?: string | null;
  /** An already-localized reason from our own copy; wins over `reason`. */
  localized?: string;
  lineLabel?: (line: string) => string;
}) {
  const { t, lang } = useLang();
  const text = localized ?? missingReasonText(reason, t, lineLabel);
  // Backend free text is English: isolate it in Arabic mode (spec 6.11).
  const foreign = lang === "ar" && !localized && !!reason && !/^missing:/.test(reason);
  return (
    <span className="missing" title={text}>
      <span aria-hidden="true">—</span>
      <span className="sr-only" {...(foreign ? { lang: "en", dir: "ltr" } : {})}>
        {text}
      </span>
    </span>
  );
}
