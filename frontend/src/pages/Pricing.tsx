import { useState } from "react";
import type { ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { useBillingPlans, useCheckout } from "../api/client";
import { useLang } from "../i18n/useLang";
import type { CopyKey } from "../i18n";
import { fmtNum } from "../i18n/format";
import { projectSavings } from "../utils/savings";
import type { BillingPlan } from "../types";

const TIER_NAME: Record<string, CopyKey> = {
  free: "plan_free_name",
  pro: "plan_pro_name",
  max: "plan_max_name",
};

const TIER_DESC: Record<string, CopyKey> = {
  free: "plan_free_desc",
  pro: "plan_pro_desc",
  max: "plan_max_desc",
};

const TIER_ORDER = ["free", "pro", "max"];

/** Deterministic savings projection — illustrative only (zborsa plan Task 14). */
function SavingsCalculator() {
  const { t, locale } = useLang();
  const [monthly, setMonthly] = useState(1000);
  const [months, setMonths] = useState(12);
  const [ratePct, setRatePct] = useState(12);
  const rows = projectSavings(monthly, months, ratePct);

  const numberField =
    (label: CopyKey, value: number, onChange: (v: number) => void, min: number) => (
      <label className="savings-field">
        <span>{t(label)}</span>
        <input
          type="number"
          min={min}
          value={value}
          onChange={(e: ChangeEvent<HTMLInputElement>) => {
            const parsed = Number.parseFloat(e.target.value);
            onChange(Number.isFinite(parsed) ? parsed : min);
          }}
        />
      </label>
    );

  return (
    <div className="pricing-card savings-card">
      <h2>{t("savings_title")}</h2>
      <div className="savings-inputs">
        {numberField("savings_monthly_amount", monthly, setMonthly, 0)}
        {numberField("savings_months", months, setMonths, 1)}
        {numberField("savings_annual_rate", ratePct, setRatePct, 0)}
      </div>
      <table className="savings-table">
        <thead>
          <tr>
            <th scope="col">{t("savings_table_month")}</th>
            <th scope="col" className="num">{t("savings_table_balance")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.month}>
              <td className="num" dir="ltr">{row.month}</td>
              <td className="num" dir="ltr">
                {fmtNum(locale, row.balance, { minimumFractionDigits: 2 })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="savings-note">{t("savings_illustrative")}</p>
    </div>
  );
}

/** Checkout only proceeds when the backend returns a provider URL. */
function PlanCheckout({ plan }: { plan: { tier: string } }) {
  const { t } = useLang();
  const checkout = useCheckout();

  if (plan.tier === "free") return null;

  const startCheckout = () => checkout.mutate({ user_key: "demo-user", tier: plan.tier });

  if (checkout.data && checkout.data.url) {
    return (
      <a className="btn btn-primary" href={checkout.data.url} target="_blank" rel="noreferrer noopener">
        {t("pricing_checkout")}
      </a>
    );
  }
  return (
    <>
      <button
        type="button"
        className="btn btn-primary"
        onClick={startCheckout}
        disabled={checkout.isPending}
      >
        {t("pricing_checkout")}
      </button>
      {checkout.isSuccess && (
        <p className="pricing-no-provider">{t("pricing_no_provider")}</p>
      )}
      {checkout.isError && (
        <p className="pricing-no-provider" role="alert">{t("pricing_checkout_error")}</p>
      )}
    </>
  );
}

export default function Pricing() {
  const { data, isLoading } = useBillingPlans();
  const { t, locale } = useLang();
  const plans = (data ?? [])
    .slice()
    .sort(
      (a: BillingPlan, b: BillingPlan) =>
        TIER_ORDER.indexOf(a.tier) - TIER_ORDER.indexOf(b.tier),
    );

  return (
    <div className="page">
      <h1>{t("pricing_title")}</h1>
      {isLoading && <p>{t("loading")}</p>}
      <div className="pricing-grid">
        {plans.map((p: BillingPlan) => {
          const nameKey = TIER_NAME[p.tier] ?? "plan_free_name";
          const descKey = TIER_DESC[p.tier] ?? "plan_free_desc";
          return (
            <div key={p.id} className={`pricing-card pricing-${p.tier}`}>
              <h2>{t(nameKey)}</h2>
              <p className="pricing-price">
                {fmtNum(locale, p.price_egp, { minimumFractionDigits: 0 })}
                {" "}
                {t("egp")}
                {" · "}
                {t("pricing_per_month")}
              </p>
              <ul className="pricing-features" title={JSON.stringify(p.entitlements)}>
                {t(descKey).split("\n").map((line: string) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <PlanCheckout plan={p} />
            </div>
          );
        })}
      </div>
      <SavingsCalculator />
      <Link to="/" className="back-link">{t("back")}</Link>
    </div>
  );
}
