import { useParams } from "react-router-dom";
import { useCompanyByTicker, useEgxMembership, usePurification, useScreeningResult } from "../api/client";
import { joinList, lineLabelKey, purificationInputKey, ruleInputKey, ruleLabelKey } from "../components/research/labels";
import { ExternalLink, ProvisionalTag, ResearchSection, TechnicalDetails } from "../components/research/parts";
import { MissingReason, Reason } from "../components/research/reasons";
import { ShariahBadge, Tag } from "../components/ui/Badges";
import DataTable, { type Column } from "../components/ui/DataTable";
import { Missing } from "../components/ui/Missing";
import { Notice } from "../components/ui/Notice";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import { fmtCycle, fmtDate, fmtNum, fmtPct, toNumber } from "../lib/format";
import type { EgxMembershipStatus, PurificationEstimate, ScreeningResult, ScreeningRuleResult, ShariahStatus } from "../types";
import { ForeignText } from "./shared/ForeignText";

type Translate = ReturnType<typeof useLang>["t"];
type Verdict = ShariahStatus["verdict"];

const VERDICTS: readonly Verdict[] = ["COMPLIANT", "NON_COMPLIANT", "INSUFFICIENT_DATA", "NOT_SCREENED"];

function verdictOf(result: ScreeningResult | null | undefined): Verdict {
  if (!result) return "NOT_SCREENED";
  return VERDICTS.find((v) => v === result.status) ?? "INSUFFICIENT_DATA";
}

/** "interest_income, total_revenue" -> localized, comma-separated line names. */
function inputNames(missing: string, t: Translate, locale: string): string {
  const names = missing
    .split(/[,\s]+/)
    .filter((token) => token !== "")
    .map((token) => {
      const key = ruleInputKey(token) ?? purificationInputKey(token) ?? lineLabelKey(token);
      return key ? t(key) : token.replace(/_/g, " ");
    });
  return joinList(locale, names);
}

const RESULT_KEY = {
  PASS: "shariah_rule_pass",
  FAIL: "shariah_rule_fail",
} as const;

function EgxBlock({ membership }: { membership: EgxMembershipStatus | null | undefined }) {
  const { t, locale } = useLang();
  const record = membership?.egx33 ?? null;
  const cycle = record ? (fmtCycle(locale, record.review_cycle) ?? record.review_cycle) : null;
  const longNote = record?.note && record.note.length > 90 ? record.note : null;
  return (
    <div className="card-surface rs-card">
      <h3 className="rs-block-title">{t("shariah_egx33")}</h3>
      {record ? (
        <>
          <div className="rs-tags">
            {record.member ? (
              <Tag>{t("shariah_egx33_member", { cycle: cycle ?? "" })}</Tag>
            ) : (
              <span className="rs-sentence">{t("shariah_egx33_not_member")}</span>
            )}
          </div>
          <dl className="rs-kv">
            <dt>{t("rh_review_cycle")}</dt>
            <dd dir="ltr">{cycle ?? <Missing />}</dd>
            <dt>{t("rh_source")}</dt>
            <dd>{record.source ? <ExternalLink href={record.source}>{t("rh_egx_link")}</ExternalLink> : <Missing />}</dd>
          </dl>
          {record.note && !longNote && (
            <p className="rs-note">
              <ForeignText>{record.note}</ForeignText>
            </p>
          )}
          {longNote && (
            <TechnicalDetails>
              <span>{longNote}</span>
            </TechnicalDetails>
          )}
        </>
      ) : (
        <p className="rs-sentence">{t("rh_egx_none")}</p>
      )}
    </div>
  );
}

/** Per-share amounts can be small, so up to 4 decimals. */
function money(locale: string, value: string | null | undefined): string | null {
  const n = toNumber(value);
  return n === null ? null : fmtNum(locale, n, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function PurificationBlock({
  purification,
  loading,
}: {
  purification: PurificationEstimate | null | undefined;
  loading: boolean;
}) {
  const { t, locale } = useLang();
  if (loading) return <LoadingState thing={t("rh_pur_title")} />;
  if (!purification) return <EmptyState>{t("rh_pur_unavailable")}</EmptyState>;

  const amount = money(locale, purification.amount_egp);
  const dps = money(locale, purification.dps);
  const ratio = fmtPct(locale, purification.ratio);
  const partial = purification.status === "ESTIMATE_PARTIAL";

  return (
    <div className="card-surface rs-card">
      {amount !== null ? (
        <>
          <p className="rs-sentence">{t("rh_pur_amount", { x: amount })}</p>
          {(partial || purification.provisional) && (
            <div className="rs-tags">
              {partial && <Tag>{t("rh_pur_partial")}</Tag>}
              {purification.provisional && <ProvisionalTag />}
            </div>
          )}
        </>
      ) : (
        <>
          <p className="rs-sentence">
            {purification.missing_input
              ? t("rh_pur_missing", { inputs: inputNames(purification.missing_input, t, locale) })
              : t("rh_pur_unavailable")}
          </p>
          {purification.reason && (
            <p className="rs-note">
              <Reason reason={purification.reason} />
            </p>
          )}
        </>
      )}
      {dps !== null && <p className="rs-note">{t("rh_pur_dps", { x: dps })}</p>}
      {ratio !== null && <p className="rs-note">{t("rh_pur_ratio", { x: ratio })}</p>}
      <p className="rs-note">{t("rh_pur_not_zakat")}</p>
    </div>
  );
}

/**
 * Shariah tab (R43 #5-#7): verdict beside the official EGX33 record (never
 * merged), the ratio checks with their thresholds, and the per-share
 * purification estimate. Everything is computed on read; nothing is entered.
 */
export default function ShariahScreening() {
  const { ticker } = useParams<{ ticker: string }>();
  const { t, locale } = useLang();
  const { data: company } = useCompanyByTicker(ticker);
  const { data: result, isLoading, error, refetch } = useScreeningResult(company?.id);
  const { data: purification, isLoading: purLoading } = usePurification(company?.id);
  const { data: membership } = useEgxMembership(company?.id);

  if (!company || isLoading) return <LoadingState thing={t("rh_thing")} />;
  if (error) return <ErrorState thing={t("rh_thing")} onRetry={() => void refetch()} />;

  const verdict = verdictOf(result);
  const screened = fmtDate(locale, result?.screened_at);
  const period = fmtDate(locale, result?.report_date);
  const rules = result?.rule_results ?? [];

  const columns: Column<ScreeningRuleResult>[] = [
    {
      id: "rule",
      header: t("rh_col_rule"),
      sticky: true,
      cell: (rule) => {
        const key = ruleLabelKey(rule.rule_name);
        return key ? t(key) : <ForeignText>{rule.rule_name}</ForeignText>;
      },
    },
    {
      id: "value",
      header: t("col_value"),
      type: "num",
      cell: (rule) => {
        const pct = fmtPct(locale, rule.value);
        if (pct !== null) return pct;
        if (rule.verdict !== "INSUFFICIENT_DATA") return rule.reason ? <Reason reason={rule.reason} /> : <Missing />;
        if (rule.missing_input === "industry") return <Missing localized={t("rh_industry_missing")} />;
        if (rule.missing_input) {
          return <Missing localized={t("missing_line", { line: inputNames(rule.missing_input, t, locale) })} />;
        }
        return <MissingReason reason={rule.reason} />;
      },
    },
    {
      id: "threshold",
      header: t("rh_col_threshold"),
      type: "num",
      cell: (rule) => {
        const pct = fmtPct(locale, rule.threshold);
        return pct !== null ? t("rh_below", { x: pct }) : t("rh_no_threshold");
      },
    },
    {
      id: "result",
      header: t("rh_col_result"),
      cell: (rule) => {
        const key = rule.verdict === "PASS" || rule.verdict === "FAIL" ? RESULT_KEY[rule.verdict] : "shariah_rule_unknown";
        return <span className="rs-status-word">{t(key)}</span>;
      },
    },
  ];

  return (
    <div className="page">
      {result?.compute_status === "failed" && <Notice variant="warning">{t("rs_compute_failed")}</Notice>}

      <ResearchSection title={t("rh_title")}>
        <div className="rs-pair">
          <div className="card-surface rs-card">
            <h3 className="rs-block-title">{t("shariah_our_verdict")}</h3>
            <div className="rs-tags">
              <ShariahBadge verdict={verdict} provisional={result?.provisional === true} />
            </div>
            {result && result.methodology_name && (
              <dl className="rs-kv">
                <dt>{t("rh_methodology")}</dt>
                <dd dir="ltr">
                  <code>{`${result.methodology_name} ${result.methodology_version}`}</code>
                </dd>
                <dt>{t("rh_screened")}</dt>
                <dd dir="ltr">{screened ?? <Missing />}</dd>
                {period !== null && (
                  <>
                    <dt>{t("rh_report_period")}</dt>
                    <dd dir="ltr">{period}</dd>
                  </>
                )}
              </dl>
            )}
            {verdict === "INSUFFICIENT_DATA" && result?.overall_reason && (
              <p className="rs-note">
                <Reason reason={result.overall_reason} />
              </p>
            )}
          </div>
          <EgxBlock membership={membership} />
        </div>
        {membership?.discrepancy.flagged && <Notice>{t("rh_discrepancy")}</Notice>}
      </ResearchSection>

      <ResearchSection title={t("rh_checks_title")}>
        <div className="rs-wrap-table">
          <DataTable
            columns={columns}
            rows={rules}
            rowKey={(rule) => rule.rule_name}
            caption={t("rh_checks_caption")}
            loadingThing={t("rh_checks_title")}
            empty={<EmptyState>{t("rh_checks_empty", { ticker: company.ticker })}</EmptyState>}
            hideDensityToggle
          />
        </div>
        {rules.some((r) => r.source) && (
          <TechnicalDetails>
            {rules.map((rule) => (
              <span key={rule.rule_name}>
                {`${rule.rule_name}: ${rule.source ?? "-"}${rule.source_date ? ` (${rule.source_date})` : ""}`}
              </span>
            ))}
          </TechnicalDetails>
        )}
      </ResearchSection>

      <ResearchSection title={t("rh_pur_title")}>
        <PurificationBlock purification={purification} loading={purLoading} />
      </ResearchSection>

      <p className="rs-note">{t("rh_footer")}</p>
    </div>
  );
}
