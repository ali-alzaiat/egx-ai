import { useEffect } from "react";
import { useLocation, useParams } from "react-router-dom";
import { useCompanyByTicker } from "../../api/client";
import InvestmentScore from "../../pages/InvestmentScore";
import Signals, { ScenarioValues, StanceFooter } from "../../pages/Signals";
import TechnicalAnalysis from "../../pages/TechnicalAnalysis";
import Thesis from "../../pages/Thesis";
import Valuation from "../../pages/Valuation";
import Disclosures from "../../pages/Disclosures";
import DataQualityCard from "../DataQualityCard";
import { LoadingState } from "../ui/States";
import DailyPrices from "./DailyPrices";
import { useLang } from "../../i18n/useLang";

/**
 * Hub tabs that stack several existing pages until their page lane rebuilds
 * them (spec 1.4: Price & signals, Valuation, Thesis & filings, Data quality).
 */

/** react-router does not scroll to `#hash` on navigation; do it for the stacked sections. */
function useScrollToHash(): void {
  const { hash } = useLocation();
  useEffect(() => {
    if (!hash) return;
    document.getElementById(hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [hash]);
}

/** Price & signals (spec 4.4.2): stance, why, limitations, levels, liquidity, indicators, scenarios, prices, footer. */
export function PriceTab() {
  return (
    <div className="page">
      <Signals />
      <TechnicalAnalysis />
      <ScenarioValues />
      <DailyPrices />
      <StanceFooter />
    </div>
  );
}

export function ValuationTab() {
  useScrollToHash();
  return (
    <div className="page">
      <Valuation />
      <section id="score">
        <InvestmentScore />
      </section>
    </div>
  );
}

export function ThesisTab() {
  useScrollToHash();
  return (
    <div className="page">
      <Thesis />
      <section id="filings">
        <Disclosures />
      </section>
    </div>
  );
}

export function QualityTab() {
  const { ticker } = useParams<{ ticker: string }>();
  const { t } = useLang();
  const { data: company } = useCompanyByTicker(ticker);
  if (!company) return <LoadingState thing={t("loading_company")} />;
  return <DataQualityCard companyId={company.id} />;
}
