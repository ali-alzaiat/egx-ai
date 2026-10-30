import { useLang } from "../../i18n/useLang";
import { fmtPct, fmtPrice } from "../../lib/format";
import type { FairValueLeg, RoeBase } from "../../types";
import DataTable, { type Column } from "../ui/DataTable";
import { Missing } from "../ui/Missing";
import { Notice } from "../ui/Notice";
import { ResearchSection } from "./parts";
import { MissingReason, Reason, localizeReason } from "./reasons";

interface Row {
  id: string;
  label: string;
  value: string | null;
  basis: string | null;
  total?: boolean;
}

type RoeRow = { kind: "year"; fiscalYear: number; roe: string | null; reason: string | null; status: string } | { kind: "mean" };

/** A decimal string the backend put in the leg's assumptions, or null. */
function assumption(leg: FairValueLeg, key: string): string | null {
  const value = leg.assumptions[key];
  return typeof value === "string" ? value : null;
}

function YearsOfRoe({ roe }: { roe: RoeBase }) {
  const { t, locale } = useLang();
  const rows: RoeRow[] = [
    ...roe.years.map((y): RoeRow => ({ kind: "year", fiscalYear: y.fiscal_year, roe: y.roe, reason: y.reason, status: y.status })),
    ...(roe.years.length > 0 ? [{ kind: "mean" } as const] : []),
  ];
  const columns: Column<RoeRow>[] = [
    {
      id: "year",
      header: t("rv_fcfe_col_year"),
      sticky: true,
      cell: (row) =>
        row.kind === "year" ? t("rv_fcfe_year", { year: row.fiscalYear }) : <strong>{t("rv_fcfe_mean", { n: roe.years_required })}</strong>,
    },
    {
      id: "roe",
      header: t("rv_ri_roe"),
      type: "num",
      cell: (row) => {
        if (row.kind === "mean") {
          const mean = fmtPct(locale, roe.mean);
          return mean !== null ? <strong>{mean}</strong> : <Missing localized={t("rv_fcfe_incomplete", { n: roe.years_required })} />;
        }
        return fmtPct(locale, row.roe) ?? <Missing reason={row.reason} />;
      },
    },
  ];
  if (roe.mean === null || roe.years.some((y) => y.status !== "AVAILABLE")) {
    columns.push({
      id: "note",
      header: t("rs_col_reason"),
      cell: (row) => {
        if (row.kind === "mean") return roe.mean === null ? t("rv_fcfe_incomplete", { n: roe.years_required }) : null;
        return row.status !== "AVAILABLE" ? <Reason reason={row.reason} /> : null;
      },
    });
  }
  return (
    <ResearchSection title={t("rv_roe_title")} lead={t("rv_roe_lead", { n: roe.years_required })}>
      <div className="rs-wrap-table">
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => (row.kind === "year" ? `y${row.fiscalYear}` : "mean")}
          caption={t("rv_roe_caption")}
          loadingThing={t("rv_roe_title")}
          empty={
            <p className="rs-note">
              <Reason reason={roe.reason} />
            </p>
          }
          hideDensityToggle
        />
      </div>
    </ResearchSection>
  );
}

/**
 * The residual-income valuation, read-only (R46 V8/V9): book value per share plus
 * the present value of the excess returns (ROE minus cost of equity) and of what
 * follows, and the ROE they rest on. Used for banks and for companies whose
 * cash-flow model failed (then a note says why).
 */
export default function ResidualIncomeModel({
  leg,
  roeBase,
  detection,
}: {
  leg: FairValueLeg;
  roeBase: RoeBase | null;
  detection: string | undefined;
}) {
  const { t, locale } = useLang();
  const available = leg.status === "AVAILABLE";
  const fallback = leg.fallback_from ? leg : null;
  const years = assumption(leg, "years_high");
  const roe = fmtPct(locale, assumption(leg, "roe"));
  const ke = fmtPct(locale, assumption(leg, "cost_of_equity"));
  const keLong = fmtPct(locale, assumption(leg, "terminal_discount_rate"));
  const growth = fmtPct(locale, assumption(leg, "terminal_growth_rate"));
  const complete = roe !== null && ke !== null && keLong !== null && growth !== null && years !== null;

  const rows: Row[] = [
    { id: "bvps", label: t("rv_ri_bvps"), value: fmtPrice(locale, assumption(leg, "bvps")), basis: null },
    {
      id: "pv_ri",
      label: t("rv_ri_pv", { years: years ?? "" }),
      value: fmtPrice(locale, assumption(leg, "pv_residual_income")),
      basis: complete ? t("rv_ri_pv_basis", { roe, ke, years }) : null,
    },
    {
      id: "pv_terminal",
      label: t("rv_ri_terminal"),
      value: fmtPrice(locale, assumption(leg, "pv_terminal")),
      basis: complete ? t("rv_ri_terminal_basis", { years, keLong, growth }) : null,
    },
    { id: "fv", label: t("rv_ri_fv"), value: fmtPrice(locale, available ? leg.value : null), basis: null, total: true },
  ];

  const columns: Column<Row>[] = [
    {
      id: "item",
      header: t("rv_ri_col_item"),
      sticky: true,
      cell: (row) => (
        <span className="rs-cell-stack">
          <span>{row.total ? <strong>{row.label}</strong> : row.label}</span>
          {row.basis !== null && <span className="rs-cell-sub">{row.basis}</span>}
        </span>
      ),
    },
    {
      id: "value",
      header: t("col_value"),
      type: "num",
      cell: (row) => {
        if (row.value === null) return <MissingReason reason={leg.reason} />;
        return row.total ? <strong>{row.value}</strong> : row.value;
      },
    },
  ];

  const detectedNote =
    fallback !== null
      ? null
      : detection === "sector"
        ? t("rv_bank_detected_sector")
        : detection?.startsWith("statement_lines")
          ? t("rv_bank_detected_lines")
          : null;
  const fallbackWhy = fallback ? (localizeReason(leg.fallback_reason, t, locale) ?? leg.fallback_reason) : null;

  return (
    <>
      <ResearchSection
        title={fallback ? t("rv_ri_title_fallback") : t("rv_bank_title")}
        lead={
          <>
            {detectedNote !== null && <>{detectedNote} </>}
            {t("rv_ri_lead")}
          </>
        }
      >
        {fallback && (
          <Notice>{t("rv_ri_fallback_note", { why: fallbackWhy ?? t("rs_no_data_reason") })}</Notice>
        )}
        <div className="rs-wrap-table">
          <DataTable
            columns={columns}
            rows={rows}
            rowKey={(row) => row.id}
            caption={t("rv_ri_caption")}
            loadingThing={t("rv_bank_title")}
            hideDensityToggle
          />
        </div>
      </ResearchSection>
      {roeBase && <YearsOfRoe roe={roeBase} />}
    </>
  );
}
