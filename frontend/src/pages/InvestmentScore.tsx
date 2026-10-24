import { useParams } from "react-router-dom";
import { useCompanyByTicker, useScore } from "../api/client";
import { SCORE_COMPONENTS, SCORE_COMPONENT_KEYS, confidenceLabelKey, type ScoreComponentKey } from "../components/research/labels";
import { ProvisionalTag, ResearchSection, TechnicalDetails } from "../components/research/parts";
import { MissingReason, Reason } from "../components/research/reasons";
import DataTable, { type Column } from "../components/ui/DataTable";
import { Notice } from "../components/ui/Notice";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtNum, fmtPct } from "../lib/format";
import type { ScoreAssessment, ScoreComponent } from "../types";

interface ComponentRow {
  key: ScoreComponentKey;
  component: ScoreComponent;
}

function oneDecimal(locale: string, value: number | null | undefined): string | null {
  if (value === null || value === undefined) return null;
  return fmtNum(locale, value, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function ScoreBody({ assessment, provisional }: { assessment: ScoreAssessment; provisional: boolean }) {
  const { t, locale } = useLang();
  const headline = assessment.headline;
  const total = oneDecimal(locale, headline.value);
  const rows: ComponentRow[] = SCORE_COMPONENTS.flatMap((key) => {
    const component = assessment.components[key];
    return component ? [{ key, component }] : [];
  });
  const weight = rows.length > 0 ? fmtPct(locale, 1 / rows.length) : null;
  const zone = assessment.buy_zone.in_buy_zone;
  const asOf = fmtDate(locale, assessment.as_of);

  const columns: Column<ComponentRow>[] = [
    { id: "component", header: t("rc_col_component"), sticky: true, cell: (row) => t(SCORE_COMPONENT_KEYS[row.key]) },
    {
      id: "score",
      header: t("rc_col_score"),
      type: "num",
      cell: (row) => oneDecimal(locale, row.component.score) ?? <MissingReason reason={row.component.reason} />,
    },
    { id: "weight", header: t("rs_col_weight"), type: "num", cell: () => weight ?? <MissingReason reason={null} /> },
    {
      id: "reason",
      header: t("rs_col_reason"),
      cell: (row) => (row.component.reason ? <Reason reason={row.component.reason} /> : "—"),
    },
  ];

  return (
    <>
      <div className="card-surface rs-hero">
        <span className="rs-hero-label">{t("rc_total")}</span>
        <div>
          {total !== null ? (
            <span className="rs-figure" dir="ltr">
              {total}
              <span className="rs-figure-unit">/ 100</span>
            </span>
          ) : (
            <span className="rs-figure">
              <MissingReason reason={headline.reason} />
            </span>
          )}
        </div>
        <p className="rs-note">
          {t("rc_confidence", {
            level: t(confidenceLabelKey(assessment.confidence.level)),
            n: assessment.n_with_data,
            total: assessment.n_checks_total,
          })}
        </p>
        {provisional && (
          <div className="rs-tags">
            <ProvisionalTag />
          </div>
        )}
      </div>

      <div className="rs-wrap-table">
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.key}
          caption={t("rc_title")}
          loadingThing={t("rc_thing")}
          footnote={t("rc_components_caption")}
          hideDensityToggle
        />
      </div>

      {typeof zone === "boolean" && (
        <div className="rs-card">
          <h3 className="rs-block-title">{t("rc_zone_title")}</h3>
          <p className="rs-sentence">{t(zone ? "rc_zone_in" : "rc_zone_out")}</p>
          <p className="rs-note">{t("rc_zone_note")}</p>
        </div>
      )}

      <p className="rs-note">
        {t("rv_footer", {
          version: assessment.methodology_version,
          asof: asOf !== null ? t("rs_as_of", { date: asOf }) : t("rs_no_data_reason"),
        })}
        {" · "}
        {t("rs_research_note")}
      </p>

      <TechnicalDetails>
        <span>{`score_methodology = ${assessment.methodology_version}`}</span>
        <span>{`valuation_methodology = ${assessment.valuation_methodology_version}`}</span>
        <span>{`profile = ${assessment.profile.profile_id} (${assessment.profile.health_track})`}</span>
        {assessment.checks.map((check) => (
          <span key={`${check.component}:${check.check_key}`}>
            {`${check.component}.${check.check_key} [${check.status}] threshold ${check.threshold || "-"}`}
          </span>
        ))}
        {assessment.checks_not_run.length > 0 && <span>{`not_run = ${assessment.checks_not_run.join(", ")}`}</span>}
      </TechnicalDetails>
    </>
  );
}

/**
 * Investment score tab section (R43 #4): five components computed on read from
 * statement lines, metrics and the fair-value snapshot. No Assess button; an
 * empty state only names why the score is unavailable.
 */
export default function InvestmentScore() {
  const { ticker } = useParams<{ ticker: string }>();
  const { t } = useLang();
  const { data: company } = useCompanyByTicker(ticker);
  const { data: score, isLoading, error, refetch } = useScore(company?.id);

  if (!company || isLoading) return <LoadingState thing={t("rc_thing")} />;
  if (error) return <ErrorState thing={t("rc_thing")} onRetry={() => void refetch()} />;

  const assessment = score?.assessment ?? null;
  return (
    <ResearchSection title={t("rc_title")}>
      {score?.compute_status === "failed" && assessment && <Notice variant="warning">{t("rs_compute_failed")}</Notice>}
      {assessment ? (
        <ScoreBody assessment={assessment} provisional={score?.provisional === true} />
      ) : (
        <>
          <EmptyState>{t("rc_empty", { ticker: company.ticker })}</EmptyState>
          {score?.compute_error && (
            <p className="rs-note">
              <Reason reason={score.compute_error} />
            </p>
          )}
        </>
      )}
    </ResearchSection>
  );
}
