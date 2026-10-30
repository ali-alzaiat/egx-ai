import { useLang } from "../../i18n/useLang";
import { fmtPct, fmtPrice, fmtRatio } from "../../lib/format";
import type { FairValueLeg } from "../../types";
import DataTable, { type Column } from "../ui/DataTable";
import { ResearchSection } from "./parts";
import { MissingReason } from "./reasons";

interface Row {
  id: string;
  label: string;
  value: string | null;
}

/** A decimal string the backend put in the leg's assumptions, or null. */
function assumption(leg: FairValueLeg, key: string): string | null {
  const value = leg.assumptions[key];
  return typeof value === "string" ? value : null;
}

/**
 * The bank valuation, read-only (R46 V3): book value per share times a justified
 * price-to-book built from ROE, cost of equity and growth. The note says why this
 * company is valued as a bank.
 */
export default function BankModel({ leg, detection }: { leg: FairValueLeg; detection: string | undefined }) {
  const { t, locale } = useLang();
  const available = leg.status === "AVAILABLE";

  const rows: Row[] = [
    { id: "bvps", label: t("rv_bank_bvps"), value: fmtPrice(locale, assumption(leg, "bvps")) },
    { id: "roe", label: t("rv_bank_roe"), value: fmtPct(locale, assumption(leg, "roe")) },
    { id: "ke", label: t("rv_bank_ke"), value: fmtPct(locale, assumption(leg, "cost_of_equity")) },
    { id: "growth", label: t("rv_bank_growth"), value: fmtPct(locale, assumption(leg, "growth")) },
    { id: "pb", label: t("rv_bank_pb"), value: fmtRatio(locale, assumption(leg, "justified_pb")) },
    { id: "fv", label: t("rv_bank_fv"), value: fmtPrice(locale, available ? leg.value : null) },
  ];

  const columns: Column<Row>[] = [
    { id: "item", header: t("rv_bank_col_item"), sticky: true, cell: (row) => row.label },
    {
      id: "value",
      header: t("col_value"),
      type: "num",
      cell: (row) => row.value ?? <MissingReason reason={leg.reason} />,
    },
  ];

  const note =
    detection === "sector"
      ? t("rv_bank_detected_sector")
      : detection?.startsWith("statement_lines")
        ? t("rv_bank_detected_lines")
        : null;

  return (
    <ResearchSection
      title={t("rv_bank_title")}
      lead={
        <>
          {note !== null && <>{note} </>}
          {t("rv_bank_lead")}
        </>
      }
    >
      <div className="rs-wrap-table">
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          caption={t("rv_bank_caption")}
          loadingThing={t("rv_bank_title")}
          hideDensityToggle
        />
      </div>
    </ResearchSection>
  );
}
