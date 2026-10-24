import type { ReactNode } from "react";
import { useLang } from "../../i18n/useLang";
import { fmtDate, fmtNum, fmtRatio, toNumber } from "../../lib/format";
import { ForeignText } from "../../pages/shared/ForeignText";
import type { FairValueAssumptions, FairValueResponse, ValuationAssumptionItem } from "../../types";
import DataTable, { type Column } from "../ui/DataTable";
import { Missing } from "../ui/Missing";
import { assumptionLabelKey, joinList } from "./labels";
import { ExternalLink, ResearchSection } from "./parts";
import { MissingReason } from "./reasons";

type Translate = ReturnType<typeof useLang>["t"];

/** Rates are shown to 2 decimals so 28.33% and 17.51% read exactly as sourced. */
function fmtRate(locale: string, value: string | null | undefined): string | null {
  const n = toNumber(value);
  if (n === null) return null;
  return `${fmtNum(locale, n * 100, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

interface Row {
  id: string;
  label: string;
  value: ReactNode;
  source: ReactNode;
  asOf: string | null;
}

function sourceOf(item: ValuationAssumptionItem | undefined): ReactNode {
  if (!item) return "—";
  return (
    <ExternalLink href={item.source_url}>
      <ForeignText>{item.source_title}</ForeignText>
    </ExternalLink>
  );
}

function latest(...items: (ValuationAssumptionItem | undefined)[]): string | null {
  const dates = items.flatMap((i) => (i ? [i.as_of] : []));
  return dates.length > 0 ? dates.reduce((a, b) => (a > b ? a : b)) : null;
}

function buildRows(
  fairValue: FairValueResponse,
  assumptions: FairValueAssumptions,
  t: Translate,
  locale: string,
): Row[] {
  const byKey = new Map(assumptions.items.map((item) => [item.key, item]));
  const stale = new Map((assumptions.stale ?? []).map((s) => [s.key, s.reason]));
  const label = (key: string): string => {
    const k = assumptionLabelKey(key);
    return k ? t(k) : key.replace(/_/g, " ");
  };
  const gap = (keys: string[]): ReactNode => {
    const staleReason = keys.map((k) => stale.get(k)).find((r) => r !== undefined);
    if (staleReason) return <MissingReason reason={staleReason} />;
    const absent = keys.filter((k) => !byKey.has(k));
    // The row label already names a single assumption, so only a multi-key gap names its parts.
    return (
      <Missing
        localized={absent.length > 1 ? t("rs_no_sourced", { what: joinList(locale, absent.map(label)) }) : t("rv_no_sourced_row")}
      />
    );
  };

  const stored = (key: string): Row => {
    const item = byKey.get(key);
    const isMultiple = key.startsWith("target_");
    return {
      id: key,
      label: label(key),
      value: item ? (isMultiple ? fmtRatio(locale, item.value) : fmtRate(locale, item.value)) : gap([key]),
      source: sourceOf(item),
      asOf: item?.as_of ?? null,
    };
  };

  const rf = byKey.get("risk_free_rate");
  const erp = byKey.get("equity_risk_premium");
  const inflation = byKey.get("long_run_inflation");
  const cap = byKey.get("nominal_gdp_growth");
  const discount = fmtRate(locale, assumptions.computed?.discount_rate ?? fairValue.inputs.discount_rate);
  const terminal = fmtRate(locale, assumptions.computed?.terminal_growth_rate ?? fairValue.inputs.terminal_growth_rate);
  const stageOne = fmtRate(
    locale,
    fairValue.inputs.resolved_growth_high ?? fairValue.inputs.revenue_growth ?? fairValue.inputs.growth_rate,
  );
  const capText = cap ? fmtRate(locale, cap.value) : null;

  return [
    {
      id: "discount_rate",
      label: label("discount_rate"),
      value: discount ?? gap(["risk_free_rate", "equity_risk_premium"]),
      source: t("rv_src_discount"),
      asOf: latest(rf, erp),
    },
    stored("risk_free_rate"),
    stored("equity_risk_premium"),
    stored("long_run_cost_of_equity"),
    {
      id: "terminal_growth_rate",
      label: label("terminal_growth_rate"),
      value: terminal ?? gap(["long_run_inflation"]),
      source: (
        <span className="rs-cell-stack">
          <span>{t("rv_src_terminal")}</span>
          {sourceOf(inflation)}
        </span>
      ),
      asOf: inflation?.as_of ?? null,
    },
    {
      id: "stage_one_growth",
      label: t("rv_a_stage1_growth"),
      value: stageOne ?? <MissingReason reason={fairValue.legs.intrinsic.reason} />,
      source: capText ? t("rv_src_growth", { cap: capText }) : t("rv_src_growth_nocap"),
      asOf: cap?.as_of ?? null,
    },
    stored("nominal_gdp_growth"),
    stored("target_pe"),
    stored("target_pb"),
    stored("target_ps"),
  ];
}

/**
 * Valuation assumptions, read-only, each with its source and date (R43 #1). A
 * key with no fresh sourced row shows as missing and names what is missing; the
 * model stays INSUFFICIENT_DATA rather than falling back to a constant.
 */
export default function AssumptionsTable({ fairValue }: { fairValue: FairValueResponse }) {
  const { t, locale } = useLang();
  const assumptions = fairValue.assumptions;
  if (!assumptions) return null;
  const rows = buildRows(fairValue, assumptions, t, locale);

  const columns: Column<Row>[] = [
    { id: "label", header: t("rv_col_assumption"), sticky: true, cell: (row) => row.label },
    { id: "value", header: t("col_value"), type: "num", cell: (row) => row.value },
    { id: "source", header: t("col_source"), cell: (row) => row.source },
    { id: "as_of", header: t("rs_col_as_of"), type: "num", cell: (row) => fmtDate(locale, row.asOf) ?? "—" },
  ];

  return (
    <ResearchSection title={t("rv_assump_title")} lead={t("rv_assump_lead")}>
      <div className="rs-wrap-table">
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          caption={t("rv_assump_caption")}
          loadingThing={t("rv_assump_title")}
          hideDensityToggle
        />
      </div>
    </ResearchSection>
  );
}
