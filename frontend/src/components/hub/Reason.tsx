import { useCallback } from "react";
import { useStatements } from "../../api/client";
import { useLang } from "../../i18n/useLang";
import { REASON_KEYS, lineFallback, parseReason } from "../../lib/reasons";
import { BackendText } from "../ui/BackendText";
import { Missing } from "../ui/Missing";

/**
 * Label for a statement line code ("current_liabilities" -> "Current
 * liabilities"). Uses the bilingual labels the statements endpoint already
 * ships (cached), and a readable fallback for codes it does not list.
 */
export function useLineLabel(ticker: string): (code: string) => string {
  const { lang } = useLang();
  const { data } = useStatements(ticker);
  return useCallback(
    (code: string) => {
      for (const p of data?.periods ?? []) {
        const hit = [...p.income, ...p.balance, ...p.cash_flow].find((l) => l.ontology_code === code);
        if (hit) return lang === "ar" ? hit.label_ar || hit.label_en : hit.label_en;
      }
      return lineFallback(code);
    },
    [data, lang],
  );
}

/** Localized text for a known reason code; null for backend free text. */
export function useLocalizedReason(ticker: string): (reason: string | null | undefined) => string | null {
  const { t } = useLang();
  const label = useLineLabel(ticker);
  return useCallback(
    (reason) => {
      const parsed = parseReason(reason);
      if (!parsed || parsed.kind === "raw") return null;
      if (parsed.kind === "default") return t(REASON_KEYS.default);
      if (parsed.kind === "prior") return t(REASON_KEYS.prior, { year: parsed.year, line: label(parsed.line) });
      return parsed.year
        ? t(REASON_KEYS.lineYear, { line: label(parsed.line), year: parsed.year })
        : t(REASON_KEYS.line, { line: label(parsed.line) });
    },
    [t, label],
  );
}

/** A reason as plain text: mapped copy for known codes, backend text isolated as English otherwise. */
export function ReasonText({ ticker, reason }: { ticker: string; reason: string | null | undefined }) {
  const localize = useLocalizedReason(ticker);
  const text = localize(reason);
  if (text) return <>{text}</>;
  const parsed = parseReason(reason);
  return parsed?.kind === "raw" ? <BackendText>{parsed.text}</BackendText> : null;
}

/** "—" with the reason as tooltip. */
export function ReasonMissing({ ticker, reason }: { ticker: string; reason: string | null | undefined }) {
  const localize = useLocalizedReason(ticker);
  const text = localize(reason);
  return text ? <Missing localized={text} /> : <Missing reason={reason} />;
}
