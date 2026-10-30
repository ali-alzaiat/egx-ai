import { useLang } from "../../i18n/useLang";
import { fmtEgpCompact, fmtPct } from "../../lib/format";
import type { DebtBase, FcfeBase, FcfeBaseYear } from "../../types";
import DataTable, { type Column } from "../ui/DataTable";
import { Missing } from "../ui/Missing";
import { ResearchSection } from "./parts";
import { Reason } from "./reasons";

type Row = { kind: "year"; year: FcfeBaseYear } | { kind: "mean" };

/** Starting debt of the cash-flow model: debt grows with the firm, so future borrowing = growth x debt (R46 V7). */
function DebtLine({ debt }: { debt: DebtBase }) {
  const { t, locale } = useLang();
  const value = debt.status === "AVAILABLE" ? fmtEgpCompact(locale, debt.value) : null;
  if (value === null || debt.fiscal_year === null) {
    return (
      <p className="rs-note">
        {t("rv_debt_unavailable")} <Reason reason={debt.reason} />
      </p>
    );
  }
  return (
    <p className="rs-note">
      {t("rv_debt_line", { debt: value, year: debt.fiscal_year })}
      {debt.basis === "vendor_omitted_zero" && <> {t("rv_debt_omitted")}</>}
    </p>
  );
}

/**
 * How the model's starting cash flow is built (R46 V7): per fiscal year the
 * operating cash flow, capex, the parent's share and the resulting flow, then the
 * average the model starts from, and the starting debt that grows with it. A year
 * with a gap shows its reason; nothing is filled in. Not shown for banks.
 */
export default function FcfeBaseTable({ base, debt }: { base: FcfeBase; debt?: DebtBase | null }) {
  const { t, locale } = useLang();
  const money = (value: string | null) => fmtEgpCompact(locale, value) ?? <Missing />;

  const rows: Row[] = [
    ...base.years.map((year): Row => ({ kind: "year", year })),
    ...(base.years.length > 0 ? [{ kind: "mean" } as const] : []),
  ];

  const columns: Column<Row>[] = [
    {
      id: "year",
      header: t("rv_fcfe_col_year"),
      sticky: true,
      cell: (row) =>
        row.kind === "year"
          ? t("rv_fcfe_year", { year: row.year.fiscal_year })
          : <strong>{t("rv_fcfe_mean", { n: base.years_required })}</strong>,
    },
    {
      id: "cfo",
      header: t("rv_fcfe_col_cfo"),
      type: "num",
      cell: (row) => (row.kind === "year" ? money(row.year.cfo) : null),
    },
    {
      id: "capex",
      header: t("rv_fcfe_col_capex"),
      type: "num",
      cell: (row) => (row.kind === "year" ? money(row.year.capex) : null),
    },
    {
      id: "pre_financing",
      header: t("rv_fcfe_col_prefin"),
      type: "num",
      cell: (row) => (row.kind === "year" ? money(row.year.pre_financing) : null),
    },
    {
      id: "parent_share",
      header: t("rv_fcfe_col_share"),
      type: "num",
      cell: (row) => (row.kind === "year" ? (fmtPct(locale, row.year.parent_share) ?? <Missing />) : null),
    },
    {
      id: "flow",
      header: t("rv_fcfe_col_flow"),
      type: "num",
      cell: (row) => {
        if (row.kind === "mean") {
          const mean = fmtEgpCompact(locale, base.mean);
          return mean !== null ? <strong>{mean}</strong> : <Missing localized={t("rv_fcfe_incomplete", { n: base.years_required })} />;
        }
        const value = fmtEgpCompact(locale, row.year.flow);
        return value ?? <Missing reason={row.year.reason} />;
      },
    },
  ];
  // The reason column exists only when a year or the average has a gap to explain.
  if (base.mean === null || base.years.some((y) => y.status !== "AVAILABLE")) {
    columns.push({
      id: "note",
      header: t("rs_col_reason"),
      cell: (row) => {
        if (row.kind === "mean") return base.mean === null ? t("rv_fcfe_incomplete", { n: base.years_required }) : null;
        return row.year.status !== "AVAILABLE" ? <Reason reason={row.year.reason} /> : null;
      },
    });
  }

  return (
    <ResearchSection title={t("rv_fcfe_title")} lead={t("rv_fcfe_lead", { n: base.years_required })}>
      <div className="rs-wrap-table">
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => (row.kind === "year" ? `y${row.year.fiscal_year}` : "mean")}
          caption={t("rv_fcfe_caption")}
          loadingThing={t("rv_fcfe_title")}
          empty={
            <p className="rs-note">
              <Reason reason={base.reason} />
            </p>
          }
          hideDensityToggle
        />
      </div>
      {debt && <DebtLine debt={debt} />}
    </ResearchSection>
  );
}
