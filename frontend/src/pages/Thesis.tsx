import { useParams } from "react-router-dom";
import { useCompanyByTicker, useThesis } from "../api/client";
import {
  catalystLabelKey,
  catalystWindowKey,
  evidenceLabelKey,
  invalidationPeriodKey,
  invalidationStatusKey,
  isPercentMetric,
  metricLabelKey,
} from "../components/research/labels";
import { ExternalLink, ProvisionalTag, ResearchSection, isHttpUrl } from "../components/research/parts";
import { MissingReason, Reason } from "../components/research/reasons";
import { Tag } from "../components/ui/Badges";
import { Missing } from "../components/ui/Missing";
import DataTable, { type Column } from "../components/ui/DataTable";
import { Notice } from "../components/ui/Notice";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtNum, fmtPct, fmtPrice, plural, toNumber } from "../lib/format";
import type { ThesisAssessment, ThesisCatalyst, ThesisInvalidation, ThesisLedgerRow } from "../types";
import { ForeignText } from "./shared/ForeignText";

type Translate = ReturnType<typeof useLang>["t"];

const SCENARIOS = ["bear", "base", "bull"] as const;
const SCENARIO_KEY = { bear: "target_bear", base: "target_base", bull: "target_bull" } as const;
/** Ledger actions written by a person (admin update), as opposed to automatic recomputes. */
const DOCUMENTED_ACTIONS: ReadonlySet<string> = new Set(["note", "status_update", "catalyst_update"]);

interface ScenarioValue {
  value: string | null;
  status: string | null;
  reason: string | null;
}

function readScenario(raw: unknown): ScenarioValue {
  if (raw === null || typeof raw !== "object") return { value: null, status: null, reason: null };
  const r = raw as Record<string, unknown>;
  return {
    value: typeof r.value === "string" ? r.value : null,
    status: typeof r.status === "string" ? r.status : null,
    reason: typeof r.reason === "string" ? r.reason : null,
  };
}

/**
 * The narrative skeleton is English template text from the backend. Status
 * tokens are dropped and the "not enough data" marker becomes a dash, so no raw
 * code reaches the page; the rest is shown as supplied, in an English span.
 */
function narrativeParagraphs(narrative: string): string[] {
  const cleaned = narrative
    .replace(/\s*\[(?:AVAILABLE|INSUFFICIENT_DATA|INVALID|OK)\]/g, "")
    .replace(/INSUFFICIENT_DATA/g, "—")
    .replace(/(\w)_(?=\w)/g, "$1 ");
  return cleaned
    .split(/(?<=\.)\s+(?=[A-Z])/)
    .map((p) => p.trim())
    .filter((p) => p !== "");
}

function metricName(code: string, t: Translate): string {
  const key = metricLabelKey(code);
  return key ? t(key) : code.replace(/_/g, " ");
}

function thresholdText(locale: string, inv: ThesisInvalidation): string {
  const n = toNumber(inv.threshold);
  if (n === null) return inv.threshold;
  return isPercentMetric(inv.metric) ? (fmtPct(locale, n / 100) ?? inv.threshold) : fmtNum(locale, n);
}

function InvalidationList({ items }: { items: ThesisInvalidation[] }) {
  const { t, locale } = useLang();
  if (items.length === 0) return <EmptyState>{t("rt_inv_empty")}</EmptyState>;
  return (
    <ul className="rs-list">
      {items.map((inv) => {
        const periodKey = invalidationPeriodKey(inv.period);
        const evidenceKey = evidenceLabelKey(inv.evidence_source);
        const statusKey = invalidationStatusKey(inv.status);
        return (
          <li key={`${inv.metric}-v${inv.version}`}>
            <span>
              {t(inv.direction === "above" ? "rt_inv_above" : "rt_inv_below", {
                metric: metricName(inv.metric, t),
                threshold: thresholdText(locale, inv),
              })}
              {inv.period && ` ${t("rt_inv_over", { period: periodKey ? t(periodKey) : inv.period })}`}{" "}
              {statusKey && <Tag>{t(statusKey)}</Tag>}
            </span>
            {inv.evidence_source && (
              <span className="rs-list-sub">
                {t("rt_inv_evidence", {
                  source: evidenceKey ? t(evidenceKey) : inv.evidence_source.replace(/_/g, " "),
                })}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function CatalystsTable({ catalysts }: { catalysts: ThesisCatalyst[] }) {
  const { t, locale } = useLang();
  const columns: Column<ThesisCatalyst>[] = [
    {
      id: "date",
      header: t("rt_col_date"),
      cell: (c) => {
        const windowKey = catalystWindowKey(c.window);
        if (windowKey) return t(windowKey);
        const from = fmtDate(locale, c.date_from);
        const to = fmtDate(locale, c.date_to);
        if (from && to && from !== to) return `${from} – ${to}`;
        return from ?? to ?? c.window ?? "—";
      },
    },
    {
      id: "catalyst",
      header: t("rt_col_catalyst"),
      cell: (c) => {
        const labelKey = catalystLabelKey(c.label);
        return (
          <span className="rs-cell-stack">
            <ForeignText>{c.event}</ForeignText>
            {labelKey && <span className="rs-cell-sub">{t(labelKey)}</span>}
          </span>
        );
      },
    },
    {
      id: "source",
      header: t("rt_col_source"),
      cell: (c) =>
        isHttpUrl(c.provenance) ? (
          <ExternalLink href={c.provenance}>{t("rt_source_link")}</ExternalLink>
        ) : c.provenance ? (
          <ForeignText>{c.provenance}</ForeignText>
        ) : (
          "—"
        ),
    },
  ];
  return (
    <div className="rs-wrap-table">
      <DataTable
        columns={columns}
        rows={catalysts}
        rowKey={(c) => c.id}
        caption={t("rt_cat_caption")}
        loadingThing={t("rt_thing")}
        empty={<EmptyState>{t("rt_cat_empty")}</EmptyState>}
        hideDensityToggle
      />
    </div>
  );
}

function Ledger({ rows }: { rows: ThesisLedgerRow[] }) {
  const { t, locale } = useLang();
  // Append-only record; newest entry first.
  const ordered = [...rows].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
  if (ordered.length === 0) return <EmptyState>{t("rt_ledger_empty")}</EmptyState>;
  return (
    <ol className="rs-timeline card-surface">
      {ordered.map((row, i) => (
        <li key={`${row.created_at ?? "undated"}-${i}`}>
          <span className="rs-timeline-date" dir="ltr">
            {fmtDate(locale, row.created_at) ?? "—"}
          </span>
          <span className="rs-timeline-body">
            <ForeignText>{row.rationale}</ForeignText>
            {DOCUMENTED_ACTIONS.has(row.action) && (
              <span className="rs-tags">
                <Tag>{t("rt_ledger_documented")}</Tag>
              </span>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}

function ThesisBody({ assessment, provisional }: { assessment: ThesisAssessment; provisional: boolean }) {
  const { t, locale } = useLang();
  const years = assessment.header.horizon_years;
  const horizon = plural(locale, years, {
    one: t("rt_horizon_one"),
    two: t("rt_horizon_two"),
    few: t("rt_horizon_few"),
    many: t("rt_horizon_many"),
    other: t("rt_horizon_other"),
  });
  const fairValue = fmtPrice(locale, assessment.header.fair_value.value);
  const triggered = assessment.needs_reassessment || assessment.invalidations.some((i) => i.status === "Triggered");
  const scenarios = SCENARIOS.map((name) => ({ name, ...readScenario(assessment.scenarios[name]) }));
  const scenarioMissing = scenarios.every((s) => fmtPrice(locale, s.status === "AVAILABLE" ? s.value : null) === null);
  const paragraphs = assessment.narrative ? narrativeParagraphs(assessment.narrative) : [];

  const scenarioColumns: Column<{ id: string }>[] = scenarios.map((s) => ({
    id: s.name,
    header: t(SCENARIO_KEY[s.name]),
    type: "num" as const,
    cell: () => fmtPrice(locale, s.status === "AVAILABLE" ? s.value : null) ?? <MissingReason reason={s.reason} />,
  }));

  return (
    <>
      {triggered && <Notice variant="warning">{t("rt_triggered")}</Notice>}

      <div className="card-surface rs-card">
        <p className="rs-sentence">{horizon}</p>
        <p className="rs-note">
          {t("rt_fair_value")}:{" "}
          {fairValue !== null ? (
            <span dir="ltr">{`${fairValue} ${t("egp")}`}</span>
          ) : (
            <Missing />
          )}
        </p>
        {provisional && (
          <div className="rs-tags">
            <ProvisionalTag />
          </div>
        )}
      </div>

      {paragraphs.length > 0 && (
        <div className="rs-card">
          <h3 className="rs-block-title">{t("rt_narrative_title")}</h3>
          <p className="rs-note">{t("rt_narrative_note")}</p>
          <div className="rs-prose">
            {paragraphs.map((p, i) => (
              <p key={i}>
                <ForeignText>{p}</ForeignText>
              </p>
            ))}
          </div>
        </div>
      )}

      <div className="rs-card">
        <h3 className="rs-block-title">{t("rt_scen_title")}</h3>
        <p className="rs-note">{t("rv_scenarios_note")}</p>
        {scenarioMissing ? (
          <p className="rs-note">
            <Reason reason={scenarios.find((s) => s.reason)?.reason ?? null} />
          </p>
        ) : (
          <DataTable
            columns={scenarioColumns}
            rows={[{ id: "range" }]}
            rowKey={(row) => row.id}
            caption={t("rt_scen_caption")}
            loadingThing={t("rt_thing")}
            hideDensityToggle
          />
        )}
      </div>

      <div className="rs-card">
        <h3 className="rs-block-title">{t("rt_inv_title")}</h3>
        <p className="rs-note">{t("rt_inv_note")}</p>
        <InvalidationList items={assessment.invalidations} />
      </div>

      <div className="rs-card">
        <h3 className="rs-block-title">{t("rt_cat_title")}</h3>
        <CatalystsTable catalysts={assessment.catalysts} />
      </div>

      <div className="rs-card">
        <h3 className="rs-block-title">{t("rt_ledger_title")}</h3>
        <p className="rs-note">{t("rt_ledger_note")}</p>
        <Ledger rows={assessment.ledger} />
      </div>

      <p className="rs-note">
        {t("rt_disclaimer")} {t("rs_research_note")}
      </p>
    </>
  );
}

/**
 * Thesis section (R43 #8-#9): assessed automatically with the methodology
 * default horizon; the ledger is a read-only timeline. Documented updates are
 * written in Admin.
 */
export default function Thesis() {
  const { ticker } = useParams<{ ticker: string }>();
  const { t } = useLang();
  const { data: company } = useCompanyByTicker(ticker);
  const { data: thesis, isLoading, error, refetch } = useThesis(company?.id);

  if (!company || isLoading) return <LoadingState thing={t("rt_thing")} />;
  if (error) return <ErrorState thing={t("rt_thing")} onRetry={() => void refetch()} />;

  const assessment = thesis?.assessment ?? null;
  return (
    <ResearchSection title={t("rt_title")}>
      {thesis?.compute_status === "failed" && assessment && <Notice variant="warning">{t("rs_compute_failed")}</Notice>}
      {assessment ? (
        <ThesisBody assessment={assessment} provisional={thesis?.provisional === true} />
      ) : (
        <>
          <EmptyState>{t("rt_empty", { ticker: company.ticker })}</EmptyState>
          {thesis?.compute_error && (
            <p className="rs-note">
              <Reason reason={thesis.compute_error} />
            </p>
          )}
        </>
      )}
    </ResearchSection>
  );
}
