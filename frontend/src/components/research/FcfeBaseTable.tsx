import { useLang } from "../../i18n/useLang";
import { fmtEgpCompact, fmtPct } from "../../lib/format";
import type { FcfeBase, FcfeBaseYear } from "../../types";
import DataTable, { type Column } from "../ui/DataTable";
import { Missing } from "../ui/Missing";
import { ResearchSection } from "./parts";
import { Reason } from "./reasons";

type Row = { kind: "year"; year: FcfeBaseYear } | { kind: "mean" };

/**
 * How the model's starting cash flow is built (R46 V1/V2): per fiscal year the
 * operating cash flow, capex, net borrowing, parent share and the resulting FCFE,
 * then the average the model starts from. A year with a gap shows its reason;
 * nothing is filled in. Not shown for banks (no FCFE base).
 */
export default function FcfeBaseTable({ base }: { base: FcfeBase }) {
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
      id: "net_borrowing",
      header: t("rv_fcfe_col_borrowing"),
      type: "num",
      cell: (row) => (row.kind === "year" ? money(row.year.net_borrowing) : null),
    },
    {
      id: "parent_share",
      header: t("rv_fcfe_col_share"),
      type: "num",
      cell: (row) => (row.kind === "year" ? (fmtPct(locale, row.year.parent_share) ?? <Missing />) : null),
    },
    {
      id: "fcfe",
      header: t("rv_fcfe_col_fcfe"),
      type: "num",
      cell: (row) => {
        if (row.kind === "mean") {
          const mean = fmtEgpCompact(locale, base.mean);
          return mean !== null ? <strong>{mean}</strong> : <Missing localized={t("rv_fcfe_incomplete", { n: base.years_required })} />;
        }
        const value = fmtEgpCompact(locale, row.year.fcfe);
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
    </ResearchSection>
  );
}
