import { useLang } from "../../i18n/useLang";
import { parseReason } from "../../lib/reasons";
import { ForeignText } from "../../pages/shared/ForeignText";
import { Missing } from "../ui/Missing";
import { assumptionLabelKey, joinList, lineLabelKey } from "./labels";

type Translate = ReturnType<typeof useLang>["t"];

/** Localized name of a statement line code; unknown codes read as plain words. */
export function lineName(code: string, t: Translate): string {
  const key = lineLabelKey(code);
  return key ? t(key) : code.replace(/_/g, " ");
}

const SOURCED_GAP = /^no sourced (.+) in valuation assumptions \S+$/;
const TTM_QUARTERS = /^TTM needs four reported quarters for \w+; got (\d+)$/;
const TTM_ONE_MISSING = /^TTM needs four reported quarters for \w+; one is missing$/;
const YOY_MISSING = /^YoY needs both legs for \w+; (current|prior) is missing$/;
const MARGIN_LEG_MISSING = /^TTM margin needs both legs; .+ TTM is missing$/;
const MARGIN_BOTH_YEARS = /^need current and prior-year TTM margins$/;
const ZERO_PRIOR = /^prior-year value is zero; percent change undefined$/;
const NO_STATEMENTS = /^no approved statement lines$/;
const NO_SNAPSHOT = /^no snapshot$/;
const COMPUTATION_FAILED = /^computation failed: (.+)$/;

/**
 * Backend reason text -> our own localized sentence. Returns null for text we do
 * not know (backend free text): the caller shows it inside a `lang="en"` span.
 */
export function localizeReason(
  reason: string | null | undefined,
  t: Translate,
  locale: string,
): string | null {
  if (!reason) return null;
  const text = reason.trim();
  const parsed = parseReason(text);
  if (parsed?.kind === "line") {
    const line = lineName(parsed.line, t);
    return parsed.year ? t("rs_missing_line_fy", { line, year: parsed.year }) : t("missing_line", { line });
  }
  if (parsed?.kind === "prior") return t("rs_no_prior", { line: lineName(parsed.line, t), year: parsed.year });
  if (parsed?.kind === "default") return t("missing_default");

  const sourced = SOURCED_GAP.exec(text);
  if (sourced?.[1]) {
    const what = sourced[1].split(/,\s*/).map((key) => {
      const label = assumptionLabelKey(key);
      return label ? t(label) : key.replace(/_/g, " ");
    });
    return t("rs_no_sourced", { what: joinList(locale, what) });
  }
  if (NO_STATEMENTS.test(text)) return t("rs_no_statements");
  if (NO_SNAPSHOT.test(text)) return t("rs_no_snapshot");
  const failed = COMPUTATION_FAILED.exec(text);
  if (failed?.[1]) {
    const why = localizeReason(failed[1], t, locale);
    return why === null ? null : t("rs_computation_failed", { why });
  }
  const quarters = TTM_QUARTERS.exec(text);
  if (quarters?.[1]) return t("rs_ttm_quarters", { n: quarters[1] });
  if (TTM_ONE_MISSING.test(text)) return t("rs_ttm_missing_quarter");
  const yoy = YOY_MISSING.exec(text);
  if (yoy?.[1]) return t("rs_yoy_missing", { leg: t(yoy[1] === "current" ? "rs_leg_current" : "rs_leg_prior") });
  if (MARGIN_LEG_MISSING.test(text)) return t("rs_margin_missing");
  if (MARGIN_BOTH_YEARS.test(text)) return t("rs_margin_both_years");
  if (ZERO_PRIOR.test(text)) return t("rs_zero_prior");
  return null;
}

/** A reason as inline text: our copy when we know the code, else the backend text isolated as English. */
export function Reason({ reason }: { reason: string | null | undefined }) {
  const { t, locale } = useLang();
  if (!reason) return <>{t("rs_no_data_reason")}</>;
  const text = localizeReason(reason, t, locale);
  return text !== null ? <>{text}</> : <ForeignText>{reason}</ForeignText>;
}

/** "—" whose tooltip and screen-reader text name why the value is missing. */
export function MissingReason({ reason }: { reason: string | null | undefined }) {
  const { t, locale } = useLang();
  const text = localizeReason(reason, t, locale);
  return text !== null ? <Missing localized={text} /> : <Missing reason={reason} />;
}
