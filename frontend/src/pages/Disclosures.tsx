import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { useCompanyByTicker, useDiffs, useDisclosureComparison, useFacts, useFilings } from "../api/client";
import {
  COMPARISON_METRICS,
  diffKindKey,
  filingTypeKey,
  metricLabelKey,
} from "../components/research/labels";
import { ExternalLink, ResearchSection } from "../components/research/parts";
import { MissingReason } from "../components/research/reasons";
import { Tag } from "../components/ui/Badges";
import DataTable, { type Column } from "../components/ui/DataTable";
import { Missing } from "../components/ui/Missing";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtEgpMillions, fmtPct, fmtPrice, fmtSignedPct, toNumber } from "../lib/format";
import type { DisclosureDiff, DisclosureFact, DisclosureFiling } from "../types";
import { ForeignText } from "./shared/ForeignText";

type Translate = ReturnType<typeof useLang>["t"];

const MINUS = "−";

/** Per-share metrics are in EGP; every other disclosed amount is shown in EGP millions. */
function amountText(locale: string, metric: string, value: string | null | undefined): string | null {
  return metric === "eps" ? fmtPrice(locale, value) : fmtEgpMillions(locale, value);
}

/** Same as `amountText` with the sign always shown (U+2212 for negatives). */
function signedAmountText(locale: string, metric: string, value: string | null | undefined): string | null {
  const n = toNumber(value);
  if (n === null) return null;
  const body = amountText(locale, metric, String(Math.abs(n)));
  if (body === null) return null;
  return n > 0 ? `+${body}` : n < 0 ? `${MINUS}${body}` : body;
}

function metricName(code: string, t: Translate): string {
  const key = metricLabelKey(code);
  return key ? t(key) : code.replace(/_/g, " ");
}

function FilingsSection({ companyId, ticker }: { companyId: string; ticker: string }) {
  const { t, locale } = useLang();
  const { data: filings, isLoading, error, refetch } = useFilings(companyId);
  const { data: facts } = useFacts(companyId);

  const parsedUrls = new Set((facts ?? []).map((f) => f.source?.filing_url).filter((u): u is string => !!u));

  const columns: Column<DisclosureFiling>[] = [
    { id: "date", header: t("rf_col_report_date"), type: "num", cell: (f) => fmtDate(locale, f.report_date) ?? <Missing /> },
    {
      id: "type",
      header: t("rf_col_type"),
      cell: (f) => {
        const key = filingTypeKey(f.filing_type);
        return key ? t(key) : f.filing_type ? <ForeignText>{f.filing_type}</ForeignText> : <Missing />;
      },
    },
    { id: "bulletin", header: t("rf_col_bulletin"), type: "num", cell: (f) => f.bulletin_id ?? <Missing /> },
    {
      id: "basis",
      header: t("rf_col_basis"),
      cell: (f) =>
        f.accounting_basis ? (
          <bdi dir="ltr" lang="en">
            {f.accounting_basis}
          </bdi>
        ) : (
          <Missing />
        ),
    },
    {
      id: "parsed",
      header: t("rf_col_parsed"),
      cell: (f) => (parsedUrls.has(f.filing_url) ? t("rs_yes") : t("rs_no")),
    },
    {
      id: "link",
      header: t("rf_col_link"),
      cell: (f) => <ExternalLink href={f.filing_url}>{t("rs_open_link")}</ExternalLink>,
    },
  ];

  return (
    <ResearchSection id="filings-registry" title={t("rf_title")}>
      {error ? (
        <ErrorState thing={t("rf_thing_filings")} onRetry={() => void refetch()} />
      ) : (
        <DataTable
          columns={columns}
          rows={filings ?? []}
          rowKey={(f) => f.id}
          caption={t("rf_registry_caption")}
          loading={isLoading}
          loadingThing={t("rf_thing_filings")}
          empty={
            <div className="empty">
              <p>{t("rf_empty", { ticker })}</p>{" "}
              <Link className="rs-text-link" to={`/admin/disclosures?ticker=${encodeURIComponent(ticker)}`}>
                {t("rf_admin_link")}
              </Link>
            </div>
          }
          hideDensityToggle
        />
      )}
    </ResearchSection>
  );
}

function FactsSection({ companyId, ticker }: { companyId: string; ticker: string }) {
  const { t, locale } = useLang();
  const { data: facts, isLoading, error, refetch } = useFacts(companyId);

  const columns: Column<DisclosureFact>[] = [
    {
      id: "metric",
      header: t("rs_col_metric"),
      sticky: true,
      cell: (f) => (
        <span className="rs-cell-stack">
          <span>{metricName(f.metric, t)}</span>
          {f.is_restated && <span className="rs-cell-sub">{t("rf_restated")}</span>}
        </span>
      ),
    },
    {
      id: "value",
      header: t("col_value"),
      type: "num",
      cell: (f) =>
        f.status === "OK" ? (amountText(locale, f.metric, f.value?.value) ?? <Missing />) : <MissingReason reason={f.value?.reason} />,
    },
    { id: "period", header: t("rs_col_period"), type: "num", cell: (f) => fmtDate(locale, f.period?.end) ?? <Missing /> },
    {
      id: "filing",
      header: t("rf_col_filing"),
      cell: (f) => {
        const date = fmtDate(locale, f.source?.report_date) ?? t("rs_open_link");
        return <ExternalLink href={f.source?.filing_url}>{date}</ExternalLink>;
      },
    },
    {
      id: "page",
      header: t("rf_col_page"),
      type: "num",
      cell: (f) => {
        const page = f.locator?.page;
        return typeof page === "number" || typeof page === "string" ? String(page) : <Missing />;
      },
    },
  ];

  return (
    <ResearchSection title={t("rf_facts_title")}>
      {error ? (
        <ErrorState thing={t("rf_thing_facts")} onRetry={() => void refetch()} />
      ) : (
        <DataTable
          columns={columns}
          rows={facts ?? []}
          rowKey={(f) => f.id}
          caption={t("rf_facts_caption")}
          loading={isLoading}
          loadingThing={t("rf_thing_facts")}
          meta={t("rf_facts_meta")}
          empty={<EmptyState>{t("rf_facts_empty", { ticker })}</EmptyState>}
          hideDensityToggle
        />
      )}
    </ResearchSection>
  );
}

interface CompareRow {
  id: "ttm" | "yoy" | "margin";
  current: ReactNode;
  prior: ReactNode;
  change: ReactNode;
  changePct: ReactNode;
}

function ComparisonSection({ companyId }: { companyId: string }) {
  const { t, locale } = useLang();
  const [metric, setMetric] = useState<string>("revenue");
  const { data, isLoading, error, refetch } = useDisclosureComparison(companyId, metric);

  const cmp = data?.comparison;
  const margin = data?.ttm_margin_vs_prior_year;
  const dash = "—";

  const rows: CompareRow[] = [];
  if (cmp && margin) {
    const yoyOk = cmp.yoy.status === "OK";
    rows.push(
      {
        id: "ttm",
        current: amountText(locale, metric, cmp.ttm.value) ?? <MissingReason reason={cmp.ttm.reason} />,
        prior: dash,
        change: dash,
        changePct: dash,
      },
      {
        id: "yoy",
        current: amountText(locale, metric, cmp.yoy.current) ?? <MissingReason reason={cmp.yoy.reason} />,
        prior: amountText(locale, metric, cmp.yoy.prior) ?? <MissingReason reason={cmp.yoy.reason} />,
        change: yoyOk
          ? (signedAmountText(locale, metric, cmp.yoy.delta) ?? <MissingReason reason={cmp.yoy.reason} />)
          : <MissingReason reason={cmp.yoy.reason} />,
        changePct: fmtSignedPct(locale, cmp.yoy.delta_pct) ?? <MissingReason reason={cmp.yoy.reason} />,
      },
      {
        id: "margin",
        current: fmtPct(locale, margin.current.value) ?? <MissingReason reason={margin.current.reason ?? margin.reason} />,
        prior: fmtPct(locale, margin.prior.value) ?? <MissingReason reason={margin.prior.reason ?? margin.reason} />,
        change: fmtSignedPct(locale, margin.delta) ?? <MissingReason reason={margin.reason} />,
        changePct: dash,
      },
    );
  }

  const measureKey = { ttm: "rf_m_ttm", yoy: "rf_m_yoy", margin: "rf_m_margin" } as const;
  const columns: Column<CompareRow>[] = [
    { id: "measure", header: t("rf_cmp_col_measure"), sticky: true, cell: (r) => t(measureKey[r.id]) },
    { id: "current", header: t("rf_cmp_col_current"), type: "num", cell: (r) => r.current },
    { id: "prior", header: t("rf_cmp_col_prior"), type: "num", cell: (r) => r.prior },
    { id: "change", header: t("rf_cmp_col_change"), type: "num", cell: (r) => r.change },
    { id: "pct", header: t("rf_cmp_col_change_pct"), type: "num", cell: (r) => r.changePct },
  ];

  const mixed = error?.message === "mixed accounting bases";
  const bases = cmp?.accounting_bases ?? [];

  return (
    <ResearchSection
      title={t("rf_cmp_title")}
      aside={
        <div className="rs-select-row">
          <label htmlFor="rf-metric">{t("rf_cmp_metric")}</label>
          <select id="rf-metric" className="rs-select" value={metric} onChange={(e) => setMetric(e.target.value)}>
            {COMPARISON_METRICS.map((code) => (
              <option key={code} value={code}>
                {metricName(code, t)}
              </option>
            ))}
          </select>
        </div>
      }
    >
      {mixed ? (
        <EmptyState>{t("rf_cmp_mixed")}</EmptyState>
      ) : error ? (
        <ErrorState thing={t("rf_thing_comparison")} onRetry={() => void refetch()} />
      ) : (
        <div className="rs-wrap-table">
          <DataTable
            columns={columns}
            rows={rows}
            rowKey={(r) => r.id}
            caption={t("rf_cmp_caption")}
            loading={isLoading}
            loadingThing={t("rf_thing_comparison")}
            meta={bases.length > 0 ? t("rf_cmp_basis", { basis: bases.join(", ") }) : undefined}
            footnote={t("rf_cmp_note")}
            hideDensityToggle
          />
        </div>
      )}
    </ResearchSection>
  );
}

function ChangesSection({ companyId }: { companyId: string }) {
  const { t, locale } = useLang();
  const { data: diffs, isLoading, error, refetch } = useDiffs(companyId);

  const line = (diff: DisclosureDiff): string => {
    const prior = amountText(locale, diff.metric, diff.prior_value) ?? "—";
    const current = amountText(locale, diff.metric, diff.current_value) ?? "—";
    const delta = signedAmountText(locale, diff.metric, diff.delta);
    const pct = fmtSignedPct(locale, diff.delta_pct);
    const change = [delta, pct].filter((x): x is string => x !== null).join(", ") || "—";
    return t("rf_change_line", { prior, current, delta: change });
  };

  return (
    <ResearchSection title={t("rf_changes_title")}>
      {isLoading ? (
        <LoadingState thing={t("rf_thing_changes")} />
      ) : error ? (
        <ErrorState thing={t("rf_thing_changes")} onRetry={() => void refetch()} />
      ) : !diffs || diffs.length === 0 ? (
        <EmptyState>{t("rf_changes_empty")}</EmptyState>
      ) : (
        <ul className="rs-list">
          {diffs.map((diff) => {
            const kind = diffKindKey(diff.kind);
            const period = [fmtDate(locale, diff.prior_period), fmtDate(locale, diff.current_period)]
              .filter((x): x is string => x !== null)
              .join(" → ");
            return (
              <li key={diff.id}>
                <span>
                  {metricName(diff.metric, t)} {kind && <Tag>{t(kind)}</Tag>}
                </span>
                <span className="rs-list-sub" dir="auto">
                  {line(diff)}
                  {period !== "" && ` · ${period}`}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </ResearchSection>
  );
}

/**
 * Filings section (R43 #11-#12): the registry, facts with their filing and page,
 * a period comparison with a metric selector, and what changed. All read-only;
 * filings are registered, uploaded and parsed in Admin.
 */
export default function Disclosures() {
  const { ticker } = useParams<{ ticker: string }>();
  const { t } = useLang();
  const { data: company } = useCompanyByTicker(ticker);
  const { data: facts } = useFacts(company?.id);

  if (!company) return <LoadingState thing={t("loading_company")} />;

  const versions = Array.from(new Set((facts ?? []).map((f) => f.methodology_version).filter((v) => v !== "")));

  return (
    <div className="page">
      <FilingsSection companyId={company.id} ticker={company.ticker} />
      <FactsSection companyId={company.id} ticker={company.ticker} />
      <ComparisonSection companyId={company.id} />
      <ChangesSection companyId={company.id} />
      {versions.length > 0 && (
        <p className="rs-note">{t("rf_footer", { version: versions.join(", ") })}</p>
      )}
    </div>
  );
}
