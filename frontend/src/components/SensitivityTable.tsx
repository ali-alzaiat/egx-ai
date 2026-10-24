import { memo } from "react";
import { useLang } from "../i18n/useLang";
import { fmtPct, fmtPrice, fmtSignedPct, toNumber } from "../lib/format";
import type { FairValueResponse } from "../types";
import { sensitivityParamKey } from "./research/labels";
import { ResearchSection } from "./research/parts";
import DataTable, { type Column } from "./ui/DataTable";
import { Missing } from "./ui/Missing";

type SensitivityRow = FairValueResponse["sensitivity"][number];

/** "−3.21%" style text from the backend to a decimal fraction; null when unparseable. */
function percentTextToFraction(text: string | number | null | undefined): number | null {
  if (text === null || text === undefined) return null;
  const n = toNumber(String(text).replace("%", "").replace("−", "-"));
  return n === null ? null : n / 100;
}

/**
 * 1-D sensitivity around the base case, next to the fair value. Read-only: an
 * explanation when the backend has no rows (nothing is assumed).
 */
function SensitivityTable({ rows, baseValue }: { rows: SensitivityRow[]; baseValue: string | null }) {
  const { t, locale } = useLang();
  const base = fmtPrice(locale, baseValue);

  const columns: Column<SensitivityRow>[] = [
    {
      id: "parameter",
      header: t("rv_col_param"),
      sticky: true,
      cell: (row) => {
        const code = typeof row.parameter === "string" ? row.parameter : null;
        const key = sensitivityParamKey(code);
        return key ? t(key) : <Missing />;
      },
    },
    {
      id: "value",
      header: t("rv_col_param_value"),
      type: "num",
      cell: (row) => fmtPct(locale, row.value) ?? <Missing />,
    },
    {
      id: "fair_value",
      header: t("rv_col_fv"),
      type: "num",
      cell: (row) => fmtPrice(locale, row.fair_value) ?? <Missing />,
    },
    {
      id: "change",
      header: t("rv_col_change"),
      type: "num",
      cell: (row) => fmtSignedPct(locale, percentTextToFraction(row.change_from_base)) ?? <Missing />,
    },
  ];

  return (
    <ResearchSection
      title={t("rv_sens_title")}
      lead={rows.length > 0 && base !== null ? t("rv_sens_lead", { base }) : undefined}
    >
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => `${String(row.parameter)}:${String(row.value)}`}
        caption={t("rv_sens_caption")}
        loadingThing={t("rv_sens_title")}
        empty={<p className="empty">{t("rv_sens_empty")}</p>}
        hideDensityToggle
      />
    </ResearchSection>
  );
}

export default memo(SensitivityTable);
