import { memo } from "react";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtPct, fmtPrice, toNumber } from "../lib/format";
import type { FairValueLeg, FairValueResponse } from "../types";
import {
  confidenceLabelKey,
  dqStatusKey,
  modelLabelKey,
  statusKey,
} from "./research/labels";
import { ProvisionalTag, ResearchSection } from "./research/parts";
import { MissingReason, Reason } from "./research/reasons";
import DataTable, { type Column } from "./ui/DataTable";
import { Missing } from "./ui/Missing";
import { Notice } from "./ui/Notice";

const LEG_ORDER = ["intrinsic", "relative", "fallback"] as const;
type LegName = (typeof LEG_ORDER)[number];

const LEG_ROLE = {
  intrinsic: "rv_leg_intrinsic",
  relative: "rv_leg_relative",
  fallback: "rv_leg_fallback",
} as const;

const VERDICT_KEY = {
  POTENTIALLY_UNDERVALUED: "rv_verdict_under",
  POTENTIALLY_OVERVALUED: "rv_verdict_over",
  AROUND_FAIR_VALUE: "rv_verdict_near",
} as const;

interface LegRow {
  name: LegName;
  leg: FairValueLeg;
  weight: string | undefined;
}

const SCENARIOS = ["bear", "base", "bull"] as const;
const SCENARIO_KEY = { bear: "target_bear", base: "target_base", bull: "target_bull" } as const;

/**
 * Weighted fair value, read-only (R43 #1): the headline estimate under the stated
 * methodology, the verdict sentence, the scenario range and the model legs. The
 * verdict comes from the backend; the UI never recomputes it.
 */
function FairValueCard({ fairValue }: { fairValue: FairValueResponse }) {
  const { t, locale } = useLang();
  const fv = fairValue.fair_value;
  const headline = fmtPrice(locale, fv.status === "AVAILABLE" ? fv.value : null);
  const price = fmtPrice(locale, fairValue.current_price.value);
  const priceDate = fmtDate(locale, fairValue.current_price.as_of);
  const verdictLabel = fairValue.verdict?.label ?? "INSUFFICIENT_DATA";
  const verdictKey = verdictLabel in VERDICT_KEY ? VERDICT_KEY[verdictLabel as keyof typeof VERDICT_KEY] : null;
  const dqStatus = fairValue.confidence.dq_status;
  const degraded = dqStatus !== "OK" && headline !== null;
  const bear = fmtPrice(locale, fairValue.scenarios.bear.value);
  const bull = fmtPrice(locale, fairValue.scenarios.bull.value);
  const margin = fmtPct(locale, fairValue.confidence.required_discount);

  const legRows: LegRow[] = LEG_ORDER.map((name) => ({
    name,
    leg: fairValue.legs[name],
    weight: fairValue.weights[name],
  }));
  const legColumns: Column<LegRow>[] = [
    {
      id: "model",
      header: t("rs_col_model"),
      sticky: true,
      cell: (row) => {
        const key = modelLabelKey(row.leg.model);
        return (
          <span className="rs-cell-stack">
            <span>{key ? t(key) : row.leg.model}</span>
            <span className="rs-cell-sub">{t(LEG_ROLE[row.name])}</span>
          </span>
        );
      },
    },
    {
      id: "value",
      header: t("col_value"),
      type: "num",
      cell: (row) => fmtPrice(locale, row.leg.status === "AVAILABLE" ? row.leg.value : null) ?? <MissingReason reason={row.leg.reason} />,
    },
    {
      id: "weight",
      header: t("rs_col_weight"),
      type: "num",
      cell: (row) => (toNumber(row.weight) === null ? <Missing /> : fmtPct(locale, row.weight)),
    },
    {
      id: "status",
      header: t("col_status"),
      cell: (row) => <span className="rs-status-word">{t(statusKey(row.leg.status))}</span>,
    },
    {
      id: "reason",
      header: t("rs_col_reason"),
      cell: (row) => (row.leg.reason ? <Reason reason={row.leg.reason} /> : "—"),
    },
  ];

  const scenarioRow = [{ id: "range" }];
  const scenarioMissing = SCENARIOS.every((name) => fmtPrice(locale, fairValue.scenarios[name].value) === null);
  const scenarioColumns: Column<{ id: string }>[] = SCENARIOS.map((name) => ({
    id: name,
    header: t(SCENARIO_KEY[name]),
    type: "num" as const,
    cell: () => {
      const s = fairValue.scenarios[name];
      return fmtPrice(locale, s.status === "AVAILABLE" ? s.value : null) ?? <MissingReason reason={s.reason} />;
    },
  }));

  return (
    <>
      <ResearchSection title={t("rv_estimate_title")} aside={fairValue.provisional ? <ProvisionalTag /> : null}>
        <div className="card-surface rs-hero">
          <span className="rs-hero-label">{t("rv_headline")}</span>
          <div>
            {headline !== null ? (
              <span className="rs-figure" dir="ltr">
                {headline}
                <span className="rs-figure-unit">{t("egp")}</span>
              </span>
            ) : (
              <span className="rs-figure">
                <MissingReason reason={fv.reason} />
              </span>
            )}
          </div>
          <p className="rs-note">
            {price !== null && priceDate !== null
              ? t("rv_price_line", { price, date: priceDate })
              : t("rv_price_missing")}
          </p>
          <p className="rs-sentence">
            {verdictKey ? (
              t(verdictKey)
            ) : (
              <>
                {t("rv_verdict_none")} (<Reason reason={fv.reason} />)
              </>
            )}
          </p>
          <p className="rs-note" title={t("rv_confidence_title")}>
            {t("rv_confidence", {
              level: t(confidenceLabelKey(fairValue.confidence.level)),
              margin: margin ?? t("rs_no_data_reason"),
            })}
          </p>
        </div>
        {degraded && (
          <Notice variant="warning">
            {t("rv_dq_notice", { status: t(dqStatusKey(dqStatus)) })}
            {bear !== null && bull !== null && <> {t("rv_range", { bear, bull })}</>}
          </Notice>
        )}
      </ResearchSection>

      <ResearchSection title={t("rv_scenarios_title")} lead={t("rv_scenarios_note")}>
        {scenarioMissing ? (
          <p className="rs-note">
            <Reason reason={fairValue.scenarios.base.reason ?? fairValue.scenarios.bear.reason ?? fv.reason} />
          </p>
        ) : (
          <DataTable
            columns={scenarioColumns}
            rows={scenarioRow}
            rowKey={(row) => row.id}
            caption={t("rv_scenarios_title")}
            loadingThing={t("rv_thing")}
            hideDensityToggle
          />
        )}
      </ResearchSection>

      <ResearchSection title={t("rv_legs_title")}>
        <div className="rs-wrap-table">
          <DataTable
            columns={legColumns}
            rows={legRows}
            rowKey={(row) => row.name}
            caption={t("rv_legs_caption")}
            loadingThing={t("rv_thing")}
            hideDensityToggle
          />
        </div>
      </ResearchSection>
    </>
  );
}

export default memo(FairValueCard);
