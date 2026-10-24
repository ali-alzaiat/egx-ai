/*
 * Shariah screening list. Two sections until one universe-wide endpoint exists
 * (spec NEEDS-BACKEND B3): the official EGX33 members beside our verdict, and
 * the companies our own methodology has screened. Results whose company can no
 * longer be resolved are hidden and counted, never shown as an id.
 */

import { useMemo } from "react";
import { useCompanies, useScreenedCompanies, useStanceRadar } from "../api/client";
import { ShariahBadge } from "../components/ui/Badges";
import DataTable, { type Column } from "../components/ui/DataTable";
import { Missing } from "../components/ui/Missing";
import { PageHeader } from "../components/ui/PageHeader";
import { PageTitle } from "../components/ui/PageTitle";
import { EmptyState, ErrorState } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import { fmtCycle, fmtDate } from "../lib/format";
import type { Company, ScreenedCompanySummary, ShariahStatus, StanceRadarItem } from "../types";
import { Stock, countText } from "./companies/shared";

type Verdict = ShariahStatus["verdict"];
const VERDICTS: readonly Verdict[] = ["COMPLIANT", "NON_COMPLIANT", "INSUFFICIENT_DATA", "NOT_SCREENED"];

function toVerdict(status: string): Verdict {
  return (VERDICTS as readonly string[]).includes(status) ? (status as Verdict) : "INSUFFICIENT_DATA";
}

interface ScreenedRow {
  summary: ScreenedCompanySummary;
  company: Company;
}

export default function Screening() {
  const { t, locale } = useLang();
  const members = useStanceRadar(50, "egx33");
  const screened = useScreenedCompanies();
  // The screening list carries company_id only; resolve tickers through the
  // full universe (page_size caps at 200).
  const universe1 = useCompanies({ page_size: 200 });
  const universe2 = useCompanies({ page_size: 200, page: 2 });

  const byId = useMemo(() => {
    const map = new Map<string, Company>();
    for (const company of [...(universe1.data?.items ?? []), ...(universe2.data?.items ?? [])]) {
      map.set(company.id, company);
    }
    return map;
  }, [universe1.data, universe2.data]);

  const resolved = useMemo(() => {
    const rows: ScreenedRow[] = [];
    let hidden = 0;
    for (const summary of screened.data ?? []) {
      const company = byId.get(summary.company_id);
      if (company) rows.push({ summary, company });
      else hidden += 1;
    }
    return { rows, hidden };
  }, [screened.data, byId]);
  const universeLoading = universe1.isLoading || universe2.isLoading;

  const memberItems = members.data?.items ?? [];
  const cycleRaw = memberItems.find((m) => m.shariah?.egx33_review_cycle)?.shariah?.egx33_review_cycle ?? null;
  const cycle = fmtCycle(locale, cycleRaw);

  const memberColumns = useMemo<Column<StanceRadarItem>[]>(
    () => [
      {
        id: "stock",
        header: t("col_stock"),
        sticky: true,
        cell: (m) => <Stock ticker={m.ticker} name={m.name} href={`/companies/${m.ticker}/shariah`} />,
      },
      {
        id: "ours",
        header: t("scr_col_our"),
        cell: (m) => <ShariahBadge verdict={m.shariah?.verdict ?? "NOT_SCREENED"} />,
      },
      {
        id: "cycle",
        header: t("scr_col_cycle"),
        cell: (m) => fmtCycle(locale, m.shariah?.egx33_review_cycle) ?? <Missing localized={t("missing_default")} />,
      },
    ],
    [t, locale],
  );

  const screenedColumns = useMemo<Column<ScreenedRow>[]>(
    () => [
      {
        id: "stock",
        header: t("col_stock"),
        sticky: true,
        cell: (r) => <Stock ticker={r.company.ticker} name={r.company.name} nameAr={r.company.name_ar} href={`/companies/${r.company.ticker}/shariah`} />,
      },
      {
        id: "ours",
        header: t("scr_col_our"),
        cell: (r) => <ShariahBadge verdict={toVerdict(r.summary.status)} />,
      },
      {
        id: "method",
        header: t("scr_col_method"),
        cell: (r) => (
          <span className="text-mono" dir="ltr">
            {r.summary.methodology_version}
          </span>
        ),
      },
      {
        id: "screened",
        header: t("scr_col_screened"),
        cell: (r) => fmtDate(locale, r.summary.screened_at) ?? <Missing localized={t("missing_default")} />,
      },
    ],
    [t, locale],
  );

  return (
    <div className="page">
      <PageTitle parts={[t("scr_title")]} />
      <PageHeader title={t("scr_title")} subtitle={t("scr_subtitle")} />

      <section aria-labelledby="scr-egx33">
        <h2 className="section-title" id="scr-egx33">
          {cycle ? t("scr_egx33_title", { cycle }) : t("scr_egx33_title_plain")}
        </h2>
        {members.isError ? (
          <ErrorState thing={t("scr_egx33_thing")} onRetry={() => void members.refetch()} />
        ) : (
          <DataTable
            columns={memberColumns}
            rows={memberItems}
            rowKey={(m) => m.company_id}
            caption={t("scr_egx33_title_plain")}
            loading={members.isLoading}
            loadingThing={t("scr_egx33_thing")}
            meta={countText(t, locale, memberItems.length, "stocks_count")}
            empty={<EmptyState>{t("scr_egx33_empty")}</EmptyState>}
            hideDensityToggle
          />
        )}
      </section>

      <section aria-labelledby="scr-ours">
        <h2 className="section-title" id="scr-ours">
          {t("scr_ours_title")}
        </h2>
        {screened.isError ? (
          <ErrorState thing={t("scr_ours_thing")} onRetry={() => void screened.refetch()} />
        ) : (
          <DataTable
            columns={screenedColumns}
            rows={resolved.rows}
            rowKey={(r) => r.summary.id}
            caption={t("scr_ours_title")}
            loading={screened.isLoading || universeLoading}
            loadingThing={t("scr_ours_thing")}
            meta={
              resolved.hidden > 0
                ? `${countText(t, locale, resolved.rows.length, "stocks_count")} · ${countText(t, locale, resolved.hidden, "hidden_results")}`
                : countText(t, locale, resolved.rows.length, "stocks_count")
            }
            empty={<EmptyState>{t("scr_ours_empty")}</EmptyState>}
            footnote={t("scr_footnote")}
            hideDensityToggle
          />
        )}
      </section>
    </div>
  );
}
