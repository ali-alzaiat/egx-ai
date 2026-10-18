import { Link } from "react-router-dom";
import { useBillingPlans } from "../api/client";
import { useLang } from "../i18n/useLang";
import type { CopyKey } from "../i18n";
import { fmtNum } from "../i18n/format";
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
              <p className="pricing-price" dir="ltr">
                {fmtNum(locale, p.price_egp, { minimumFractionDigits: 0 })}
                {" "}
                {t("egp")}
                {" · "}
                {t("pricing_per_month")}
              </p>
              <p className="pricing-features" title={JSON.stringify(p.entitlements)}>
                {t(descKey)}
              </p>
            </div>
          );
        })}
      </div>
      <Link to="/">{t("back")}</Link>
    </div>
  );
}
