import type { CopyKey } from "../../i18n";

/*
 * Backend codes -> localized copy keys for the research tabs. Helpers return a
 * key (never English text) so the caller localizes with t(); a code with no
 * entry returns null and the caller shows the backend text in a `lang="en"`
 * span (or a muted fallback).
 */

type KeyMap = ReadonlyMap<string, CopyKey>;

function pick(map: KeyMap, code: string | null | undefined): CopyKey | null {
  return code ? (map.get(code) ?? null) : null;
}

const LINES: KeyMap = new Map<string, CopyKey>([
  ["revenue", "rl_revenue"],
  ["cost_of_revenue", "rl_cost_of_revenue"],
  ["gross_profit", "rl_gross_profit"],
  ["operating_profit", "rl_operating_profit"],
  ["net_income", "rl_net_income"],
  ["eps", "rl_eps"],
  ["interest_income", "rl_interest_income"],
  ["finance_costs", "rl_finance_costs"],
  ["total_assets", "rl_total_assets"],
  ["current_assets", "rl_current_assets"],
  ["cash_and_equivalents", "rl_cash_and_equivalents"],
  ["inventory", "rl_inventory"],
  ["total_liabilities", "rl_total_liabilities"],
  ["current_liabilities", "rl_current_liabilities"],
  ["interest_bearing_debt", "rl_interest_bearing_debt"],
  ["total_equity", "rl_total_equity"],
  ["shares_outstanding", "rl_shares_outstanding"],
  ["cfo", "rl_cfo"],
  ["capex", "rl_capex"],
  ["dividends_paid", "rl_dividends_paid"],
  ["weighted_avg_shares_basic", "rl_weighted_avg_shares_basic"],
]);
export const lineLabelKey = (code: string | null | undefined): CopyKey | null => pick(LINES, code);

const METRICS: KeyMap = new Map<string, CopyKey>([
  ["revenue", "rm_revenue"],
  ["net_income", "rm_net_income"],
  ["total_assets", "rm_total_assets"],
  ["total_equity", "rm_total_equity"],
  ["eps", "rm_eps"],
  ["revenue_growth_yoy", "rm_revenue_growth_yoy"],
  ["net_income_growth_yoy", "rm_net_income_growth_yoy"],
  ["eps_growth_yoy", "rm_eps_growth_yoy"],
  ["gross_margin", "rm_gross_margin"],
  ["operating_margin", "rm_operating_margin"],
  ["net_margin", "rm_net_margin"],
  ["roe", "rm_roe"],
  ["roa", "rm_roa"],
  ["debt_to_equity", "rm_debt_to_equity"],
  ["debt_to_assets", "rm_debt_to_assets"],
  ["current_ratio", "rm_current_ratio"],
  ["quick_ratio", "rm_quick_ratio"],
  ["operating_cash_flow_margin", "rm_operating_cash_flow_margin"],
  ["free_cash_flow", "rm_free_cash_flow"],
  ["free_cash_flow_margin", "rm_free_cash_flow_margin"],
  ["book_value_per_share", "rm_book_value_per_share"],
]);
export const metricLabelKey = (code: string | null | undefined): CopyKey | null => pick(METRICS, code);

/** Metrics stored as percentage points (47.9 means 47.9%), per the backend `unit` "%". */
const PERCENT_METRICS: ReadonlySet<string> = new Set([
  "revenue_growth_yoy",
  "net_income_growth_yoy",
  "eps_growth_yoy",
  "gross_margin",
  "operating_margin",
  "net_margin",
  "roe",
  "roa",
  "operating_cash_flow_margin",
  "free_cash_flow_margin",
]);
export const isPercentMetric = (code: string): boolean => PERCENT_METRICS.has(code);

const MODELS: KeyMap = new Map<string, CopyKey>([
  ["fcfe_two_stage", "rd_fcfe_two_stage"],
  ["price_to_earnings", "rd_price_to_earnings"],
  ["price_to_book", "rd_price_to_book"],
  ["price_to_sales", "rd_price_to_sales"],
  ["ev_to_ebitda", "rd_ev_to_ebitda"],
  ["discounted_cash_flow", "rd_discounted_cash_flow"],
  ["dividend_discount", "rd_dividend_discount"],
  ["excess_returns", "rd_excess_returns"],
  ["affo_two_stage", "rd_affo_two_stage"],
]);
export const modelLabelKey = (code: string | null | undefined): CopyKey | null => pick(MODELS, code);

const ASSUMPTIONS: KeyMap = new Map<string, CopyKey>([
  ["discount_rate", "rv_a_discount_rate"],
  ["terminal_growth_rate", "rv_a_terminal_growth"],
  ["risk_free_rate", "rv_a_risk_free_rate"],
  ["equity_risk_premium", "rv_a_equity_risk_premium"],
  ["long_run_inflation", "rv_a_long_run_inflation"],
  ["long_run_cost_of_equity", "rv_a_long_run_cost_of_equity"],
  ["nominal_gdp_growth", "rv_a_nominal_gdp_growth"],
  ["target_pe", "rv_a_target_pe"],
  ["target_pb", "rv_a_target_pb"],
  ["target_ps", "rv_a_target_ps"],
]);
export const assumptionLabelKey = (code: string | null | undefined): CopyKey | null => pick(ASSUMPTIONS, code);

const SENSITIVITY_PARAMS: KeyMap = new Map<string, CopyKey>([
  ["discount_rate", "rv_p_discount_rate"],
  ["revenue_growth", "rv_p_revenue_growth"],
]);
export const sensitivityParamKey = (code: string | null | undefined): CopyKey | null =>
  pick(SENSITIVITY_PARAMS, code);

const CONFIDENCE: KeyMap = new Map<string, CopyKey>([
  ["VeryHigh", "rs_conf_veryhigh"],
  ["High", "rs_conf_high"],
  ["Medium", "rs_conf_medium"],
  ["Low", "rs_conf_low"],
]);
/** Unknown levels read as "not rated" rather than being guessed. */
export const confidenceLabelKey = (level: string | null | undefined): CopyKey =>
  pick(CONFIDENCE, level) ?? "rs_conf_unrated";

const DQ_STATUS: KeyMap = new Map<string, CopyKey>([
  ["OK", "rs_dq_ok"],
  ["DEGRADED", "rs_dq_degraded"],
  ["POOR", "rs_dq_poor"],
  ["MISSING", "rs_dq_missing"],
]);
export const dqStatusKey = (status: string | null | undefined): CopyKey => pick(DQ_STATUS, status) ?? "rs_dq_missing";

/** AVAILABLE / INSUFFICIENT_DATA / INVALID / NOT_RUN as a word. */
export function statusKey(status: string): CopyKey {
  if (status === "AVAILABLE" || status === "PASS" || status === "OK") return "rs_status_available";
  if (status === "INVALID") return "rs_status_invalid";
  if (status === "NOT_RUN") return "rs_status_not_run";
  return "rs_status_insufficient";
}

const RULES: KeyMap = new Map<string, CopyKey>([
  ["debt_ratio", "rh_r_debt_ratio"],
  ["interest_income_ratio", "rh_r_interest_income_ratio"],
  ["cash_securities_ratio", "rh_r_cash_securities_ratio"],
  ["industry_screen", "rh_r_industry_screen"],
]);
export const ruleLabelKey = (name: string | null | undefined): CopyKey | null => pick(RULES, name);

/** Purification `missing_input` tokens (rule inputs and DPS parts). */
const PURIFICATION_INPUTS: KeyMap = new Map<string, CopyKey>([
  ["total_debt", "rh_input_total_debt"],
  ["total_revenue", "rh_input_total_revenue"],
  ["revenue", "rh_input_total_revenue"],
  ["non_permissible_revenue", "rh_input_non_permissible_revenue"],
  ["interest_income", "rh_input_non_permissible_revenue"],
  ["dps", "rh_input_dps"],
  ["ratio", "rh_input_ratio"],
]);
export const purificationInputKey = (token: string): CopyKey | null => pick(PURIFICATION_INPUTS, token);

const EVIDENCE: KeyMap = new Map<string, CopyKey>([
  ["material_news_disclosure", "rt_ev_material_news_disclosure"],
  ["quarterly_shareholder_report", "rt_ev_quarterly_shareholder_report"],
  ["annual_financial_statements", "rt_ev_annual_financial_statements"],
  ["quarterly_financial_statements", "rt_ev_quarterly_financial_statements"],
  ["board_resolution_summary", "rt_ev_board_resolution_summary"],
  ["distribution_disclosure", "rt_ev_distribution_disclosure"],
]);
export const evidenceLabelKey = (code: string | null | undefined): CopyKey | null => pick(EVIDENCE, code);

const INVALIDATION_PERIODS: KeyMap = new Map<string, CopyKey>([
  ["two consecutive quarters", "rt_period_two_quarters"],
  ["annual", "rt_period_annual"],
]);
export const invalidationPeriodKey = (period: string | null | undefined): CopyKey | null =>
  pick(INVALIDATION_PERIODS, period);

const INVALIDATION_STATUS: KeyMap = new Map<string, CopyKey>([
  ["Active", "rt_status_active"],
  ["Triggered", "rt_status_triggered"],
  ["Reassessed", "rt_status_reassessed"],
]);
export const invalidationStatusKey = (status: string | null | undefined): CopyKey | null =>
  pick(INVALIDATION_STATUS, status);

const WINDOWS: KeyMap = new Map<string, CopyKey>([
  ["annual", "rt_win_annual"],
  ["quarterly", "rt_win_quarterly"],
  ["as declared", "rt_win_as_declared"],
]);
export const catalystWindowKey = (window: string | null | undefined): CopyKey | null => pick(WINDOWS, window);

const CATALYST_LABEL: KeyMap = new Map<string, CopyKey>([
  ["Confirmed", "rt_label_confirmed"],
  ["Tentative", "rt_label_tentative"],
]);
export const catalystLabelKey = (label: string | null | undefined): CopyKey | null => pick(CATALYST_LABEL, label);

const FILING_TYPES: KeyMap = new Map<string, CopyKey>([
  ["Q", "rf_type_q"],
  ["H1", "rf_type_h1"],
  ["9M", "rf_type_9m"],
  ["FY", "rf_type_fy"],
  ["BOARD", "rf_type_board"],
  ["AGM", "rf_type_agm"],
  ["MATERIAL", "rf_type_material"],
]);
export const filingTypeKey = (type: string | null | undefined): CopyKey | null => pick(FILING_TYPES, type);

const DIFF_KINDS: KeyMap = new Map<string, CopyKey>([
  ["restatement", "rf_k_restatement"],
  ["period_diff", "rf_k_period_diff"],
]);
export const diffKindKey = (kind: string | null | undefined): CopyKey | null => pick(DIFF_KINDS, kind);

const PEER_BASIS: KeyMap = new Map<string, CopyKey>([
  ["override", "rp_basis_override"],
  ["egx_sector", "rp_basis_egx_sector"],
  ["gics_sub_industry", "rp_basis_gics"],
  ["none", "rp_basis_none"],
]);
export const peerBasisKey = (basis: string | null | undefined): CopyKey | null => pick(PEER_BASIS, basis);

/** The five score components in display order. */
export const SCORE_COMPONENTS = ["value", "past", "health", "dividend", "growth"] as const;
export type ScoreComponentKey = (typeof SCORE_COMPONENTS)[number];
export const SCORE_COMPONENT_KEYS: Readonly<Record<ScoreComponentKey, CopyKey>> = {
  value: "rc_c_value",
  past: "rc_c_past",
  health: "rc_c_health",
  dividend: "rc_c_dividend",
  growth: "rc_c_growth",
};

/** Metrics offered in the period-comparison selector (R43 #12). */
export const COMPARISON_METRICS = ["revenue", "net_income", "total_assets", "total_equity", "eps"] as const;

/** Shariah rule-input labels (`missing_input`) -> the statement line that feeds them. */
const RULE_INPUTS: KeyMap = new Map<string, CopyKey>([
  ["total_debt", "rl_interest_bearing_debt"],
  ["total_assets", "rl_total_assets"],
  ["interest_income", "rl_interest_income"],
  ["total_revenue", "rl_revenue"],
  ["cash_and_equivalents", "rl_cash_and_equivalents"],
]);
export const ruleInputKey = (token: string): CopyKey | null => pick(RULE_INPUTS, token);

interface ListFormatLike {
  format(items: readonly string[]): string;
}
type ListFormatCtor = new (locale: string, options: { style: "long"; type: "conjunction" }) => ListFormatLike;

/** "A, B and C" / "أ وب وج": a localized list, so Arabic uses its own conjunction. */
export function joinList(locale: string, items: readonly string[]): string {
  // Intl.ListFormat is ES2021; the project lib is ES2020, so it is reached through a narrow cast.
  const ListFormat = (Intl as unknown as { ListFormat?: ListFormatCtor }).ListFormat;
  return ListFormat ? new ListFormat(locale, { style: "long", type: "conjunction" }).format(items) : items.join(", ");
}
