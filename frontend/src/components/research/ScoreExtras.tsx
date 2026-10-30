import type { ReactNode } from "react";
import { Badge } from "@/components/shadcn/badge";
import type { CopyKey } from "../../i18n";
import { useLang } from "../../i18n/useLang";
import { fmtEgpCompact, fmtInt, fmtPct, fmtRatio } from "../../lib/format";
import { ForeignText } from "../../pages/shared/ForeignText";
import type { DividendMetric, DividendSafetyBlock, DividendYear, PiotroskiBlock, PiotroskiCheck } from "../../types";
import { Missing } from "../ui/Missing";
import { ProvisionalTag, TechnicalDetails } from "./parts";
import { localizeReason, lineName } from "./reasons";

type Translate = ReturnType<typeof useLang>["t"];

/**
 * R47 Q1/Q2: the Piotroski F-Score and dividend-safety cards. They sit beside the
 * investment score and are not part of it. A value that could not be computed is
 * "Insufficient data" or "Not meaningful" with its reason, never zero.
 */

const CHECK_LABELS: ReadonlyMap<string, CopyKey> = new Map<string, CopyKey>([
  ["roa_positive", "rx_chk_roa_positive"],
  ["cfo_positive", "rx_chk_cfo_positive"],
  ["roa_improving", "rx_chk_roa_improving"],
  ["accruals_cash_backed", "rx_chk_accruals_cash_backed"],
  ["leverage_falling", "rx_chk_leverage_falling"],
  ["current_ratio_improving", "rx_chk_current_ratio_improving"],
  ["no_new_shares", "rx_chk_no_new_shares"],
  ["gross_margin_improving", "rx_chk_gross_margin_improving"],
  ["asset_turnover_improving", "rx_chk_asset_turnover_improving"],
]);

const GROUP_LABELS: ReadonlyMap<string, CopyKey> = new Map<string, CopyKey>([
  ["profitability", "rx_grp_profitability"],
  ["leverage_liquidity", "rx_grp_leverage_liquidity"],
  ["operating_efficiency", "rx_grp_operating_efficiency"],
]);

/** Checks whose ratio is a share of assets or revenue (shown as a percent); the rest are multiples. */
const PERCENT_RATIO_CHECKS: ReadonlySet<string> = new Set([
  "roa_positive",
  "roa_improving",
  "leverage_falling",
  "gross_margin_improving",
]);

const RATIO_LABELS: ReadonlyMap<string, CopyKey> = new Map<string, CopyKey>([
  ["ratio", "rx_in_ratio"],
  ["ratio_now", "rx_in_ratio_now"],
  ["ratio_prior", "rx_in_ratio_prior"],
]);

const SHARES_ROSE = "share count rose; a bonus issue or split is not distinguished from new equity";
const NO_ANNUAL_LINES = "no approved annual statement lines";
const NO_STATEMENTS_FY = /^no approved annual statements for FY(\d{4})$/;
const NOT_POSITIVE = /^(.+) is not positive \(FY(\d{4})\): ratio undefined$/;
const NOT_READ_AS_NO_DIVIDEND = "; not read as no dividend";

/** "Interest-bearing debt FY2025" label and a formatted value (null when the input was missing). */
function inputView(
  key: string,
  value: string | null,
  checkKey: string,
  t: Translate,
  locale: string,
): { label: string; text: string | null } {
  const ratioLabel = RATIO_LABELS.get(key);
  if (ratioLabel) {
    const text = PERCENT_RATIO_CHECKS.has(checkKey)
      ? fmtPct(locale, value)
      : (() => {
          const n = fmtRatio(locale, value);
          return n === null ? null : t("rx_times", { n });
        })();
    return { label: t(ratioLabel), text };
  }
  const line = /^(\w+)_FY(\d{4})$/.exec(key);
  const code = line?.[1];
  const year = line?.[2];
  if (code && year) {
    const text = code === "shares_outstanding" ? fmtInt(locale, value) : fmtEgpCompact(locale, value);
    return { label: t("rx_in_line_fy", { line: lineName(code, t), year }), text };
  }
  return { label: key, text: fmtRatio(locale, value) };
}

/** Our own sentence for a Piotroski reason; backend free text stays isolated English. */
function PiotroskiReason({ reason }: { reason: string }) {
  const { t, locale } = useLang();
  if (reason === SHARES_ROSE) return <>{t("rx_pio_shares_rose")}</>;
  if (reason === NO_ANNUAL_LINES) return <>{t("rs_no_statements")}</>;
  const noStatements = NO_STATEMENTS_FY.exec(reason);
  if (noStatements?.[1]) return <>{t("rx_pio_no_statements", { year: noStatements[1] })}</>;
  const notPositive = NOT_POSITIVE.exec(reason);
  if (notPositive?.[1] && notPositive[2]) {
    return <>{t("rx_pio_not_positive", { line: lineName(notPositive[1].replace(/ /g, "_"), t), year: notPositive[2] })}</>;
  }
  const known = localizeReason(reason, t, locale);
  return known !== null ? <>{known}</> : <ForeignText>{reason}</ForeignText>;
}

function ResultBadge({ status }: { status: PiotroskiCheck["status"] }) {
  const { t } = useLang();
  if (status === "PASS") return <Badge variant="gain">{t("rx_pass")}</Badge>;
  if (status === "FAIL") return <Badge variant="loss">{t("rx_fail")}</Badge>;
  return <Badge variant="muted">{t("rx_insufficient")}</Badge>;
}

function CheckItem({ check }: { check: PiotroskiCheck }) {
  const { t, locale } = useLang();
  const labelKey = CHECK_LABELS.get(check.key);
  const groupKey = GROUP_LABELS.get(check.group);
  const entries = Object.entries(check.inputs);
  return (
    <li className="rx-check">
      <div className="rx-check-head">
        <div className="rs-cell-stack">
          <span>{labelKey ? t(labelKey) : <ForeignText>{check.label}</ForeignText>}</span>
          {groupKey && <span className="rs-cell-sub">{t(groupKey)}</span>}
        </div>
        <ResultBadge status={check.status} />
      </div>
      {check.reason && (
        <p className="rs-note">
          <PiotroskiReason reason={check.reason} />
        </p>
      )}
      {entries.length > 0 && (
        <dl className="rs-kv rx-inputs">
          {entries.map(([key, value]) => {
            const view = inputView(key, value, check.key, t, locale);
            return (
              <div key={key} className="rx-input">
                <dt>{view.label}</dt>
                <dd dir="ltr">{view.text ?? <Missing localized={t("missing_default")} />}</dd>
              </div>
            );
          })}
        </dl>
      )}
    </li>
  );
}

export function PiotroskiCard({ block }: { block: PiotroskiBlock }) {
  const { t } = useLang();
  const ran = block.passes !== null && block.status === "AVAILABLE";
  const hero = ran
    ? block.checks_run === block.checks_total
      ? t("rx_pio_hero", { n: block.passes ?? 0 })
      : t("rx_pio_hero_partial", { n: block.passes ?? 0, run: block.checks_run })
    : null;
  const periods =
    block.fiscal_year !== null && block.prior_fiscal_year !== null
      ? t("rx_pio_periods", { year: block.fiscal_year, prior: block.prior_fiscal_year })
      : null;

  return (
    <div className="card-surface rs-card" role="group" aria-labelledby="rx-pio-title">
      <div className="rx-card-head">
        <h3 className="rs-block-title" id="rx-pio-title">
          {t("rx_pio_title")}
        </h3>
        {block.provisional && block.status === "AVAILABLE" && <ProvisionalTag />}
      </div>
      <p className="rs-note">{t("rx_pio_lead")}</p>

      {block.status === "NOT_RUN" && <p className="rs-sentence">{t("rx_pio_bank")}</p>}
      {block.status === "INSUFFICIENT_DATA" && (
        <p className="rs-sentence">
          {block.checks.length > 0 || !block.reason ? t("rx_pio_none") : <PiotroskiReason reason={block.reason} />}
        </p>
      )}
      {hero !== null && (
        <>
          <span className="rs-figure">{hero}</span>
          {block.checks_run < block.checks_total && (
            <p className="rs-note">{t("rx_pio_ran", { run: block.checks_run, total: block.checks_total })}</p>
          )}
        </>
      )}
      {periods !== null && block.status !== "NOT_RUN" && <p className="rs-note">{periods}</p>}

      {block.checks.length > 0 && (
        <ul className="rx-checks" aria-label={t("rx_pio_title")}>
          {block.checks.map((check) => (
            <CheckItem key={check.key} check={check} />
          ))}
        </ul>
      )}

      {block.checks.length > 0 && <p className="rs-note">{t("rx_pio_unit_note")}</p>}
      <TechnicalDetails>
        <span>{`piotroski_methodology = ${block.version}`}</span>
        {block.reason && <span>{block.reason}</span>}
        {block.deviations.map((d) => (
          <span key={d}>{d}</span>
        ))}
      </TechnicalDetails>
    </div>
  );
}

/** Reason of a dividend metric in our own words; unknown backend text stays isolated English. */
function DividendReason({ reason }: { reason: string }) {
  const { t, locale } = useLang();
  const notRead = reason.includes(NOT_READ_AS_NO_DIVIDEND);
  const base = notRead ? reason.replace(NOT_READ_AS_NO_DIVIDEND, "") : reason;
  let text: string | null = null;
  if (/^no dividends paid/.test(base)) text = t("rx_div_nm_nodiv");
  else if (/^net income to common holders is not positive/.test(base)) text = t("rx_div_nm_ni");
  else if (/^operating cash flow of a bank/.test(base)) text = t("rx_div_nm_bank");
  else {
    const noStatements = NO_STATEMENTS_FY.exec(base);
    text = noStatements?.[1] ? t("rx_pio_no_statements", { year: noStatements[1] }) : localizeReason(base, t, locale);
  }
  if (text === null) return <ForeignText>{reason}</ForeignText>;
  return <>{notRead ? `${text}; ${t("rx_div_not_no_div")}` : text}</>;
}

function MetricCell({
  metric,
  format,
  skipReason,
}: {
  metric: DividendMetric;
  format: (value: string | null) => string | null;
  /** The year-level reason is shown once, under the first column that has it. */
  skipReason?: boolean;
}) {
  const { t } = useLang();
  if (metric.status === "AVAILABLE") {
    const text = format(metric.value);
    return text !== null ? <span dir="ltr">{text}</span> : <Missing localized={t("missing_default")} />;
  }
  const word = metric.status === "NOT_MEANINGFUL" ? t("rx_not_meaningful") : t("rx_insufficient");
  return (
    <span className="rs-cell-stack">
      <span className="rs-status-word">{word}</span>
      {metric.reason && !skipReason && (
        <span className="rs-cell-sub">
          <DividendReason reason={metric.reason} />
        </span>
      )}
    </span>
  );
}

function YearItem({ row }: { row: DividendYear }) {
  const { t, locale } = useLang();
  const payout = (value: string | null): string | null => fmtPct(locale, value);
  const coverage = (value: string | null): string | null => {
    const n = fmtRatio(locale, value);
    return n === null ? null : t("rx_times", { n });
  };
  const sameReason = row.cash_coverage.reason !== null && row.cash_coverage.reason === row.payout_ratio.reason;
  return (
    <li className="rx-check">
      <div className="rs-cell-stack rx-year">
        <span dir="ltr">{t("rx_div_year", { year: row.fiscal_year })}</span>
        {row.status === "NO_DIVIDEND" && <span className="rs-cell-sub">{t("rx_div_no_dividend")}</span>}
      </div>
      <dl className="rs-kv rx-inputs">
        <div className="rx-input">
          <dt>{t("rx_div_col_payout")}</dt>
          <dd>
            <MetricCell metric={row.payout_ratio} format={payout} />
          </dd>
        </div>
        <div className="rx-input">
          <dt>{t("rx_div_col_cover")}</dt>
          <dd>
            <MetricCell metric={row.cash_coverage} format={coverage} skipReason={sameReason} />
          </dd>
        </div>
      </dl>
    </li>
  );
}

export function DividendSafetyCard({ block }: { block: DividendSafetyBlock }) {
  const { t } = useLang();
  return (
    <div className="card-surface rs-card" role="group" aria-labelledby="rx-div-title">
      <div className="rx-card-head">
        <h3 className="rs-block-title" id="rx-div-title">
          {t("rx_div_title")}
        </h3>
        {block.provisional && block.status === "AVAILABLE" && <ProvisionalTag />}
      </div>
      <p className="rs-note">
        <strong>{t("rx_div_label")}</strong>
        {" · "}
        {t("rx_div_lead")}
      </p>

      {block.years.length === 0 ? (
        <p className="rs-sentence">{t("rx_div_empty")}</p>
      ) : (
        <ul className="rx-checks" aria-label={t("rx_div_title")}>
          {block.years.map((row) => (
            <YearItem key={row.fiscal_year} row={row} />
          ))}
        </ul>
      )}

      <p className="rs-note">{t("rx_div_formulas")}</p>
      <TechnicalDetails>
        <span>{`dividend_safety_methodology = ${block.version}`}</span>
        <span>{`label = ${block.label}`}</span>
        <span>{`payout_ratio = ${block.payout_formula}`}</span>
        <span>{`cash_coverage = ${block.coverage_formula}`}</span>
      </TechnicalDetails>
    </div>
  );
}

/** The two cards, stacked, with one line saying they are not part of the score. */
export function ScoreExtras({
  piotroski,
  dividendSafety,
}: {
  piotroski: PiotroskiBlock | undefined;
  dividendSafety: DividendSafetyBlock | undefined;
}): ReactNode {
  const { t } = useLang();
  if (!piotroski && !dividendSafety) return null;
  return (
    <section className="rs-stack" aria-labelledby="rx-extras-title">
      <div className="rs-card">
        <h3 className="rs-block-title" id="rx-extras-title">
          {t("rx_extras_title")}
        </h3>
        <p className="rs-note">{t("rx_extras_lead")}</p>
      </div>
      {piotroski && <PiotroskiCard block={piotroski} />}
      {dividendSafety && <DividendSafetyCard block={dividendSafety} />}
    </section>
  );
}
