import type { ReactNode } from "react";
import { useLang } from "../../i18n/useLang";
import { fmtPct } from "../../lib/format";
import type { FairValueImplied } from "../../types";
import { InfoPopover } from "../ui/InfoPopover";
import { Reason } from "./reasons";

/** Length of the model's explicit stage (backend valuation/constants.py EXPLICIT_STAGE_YEARS). */
const STAGE_ONE_YEARS = 5;

/**
 * What the price implies under the model (R46 V6), beside the verdict: the
 * stage-1 growth that makes the model equal the price (a bank: the ROE it
 * implies), against the economy cap (a bank: its own ROE). It explains the
 * verdict and never changes it. When the backend cannot solve it, the reason shows.
 */
export default function ImpliedPrice({ implied }: { implied: FairValueImplied }) {
  const { t, locale } = useLang();
  const isRoe = implied.metric === "roe";
  const value = fmtPct(locale, implied.status === "AVAILABLE" ? implied.value : null);
  const compare = fmtPct(locale, implied.compare_to.value);

  let sentence: ReactNode;
  if (value === null) {
    // The label above already says what is missing; the reason is the sentence.
    sentence = <Reason reason={implied.reason} />;
  } else if (isRoe) {
    sentence =
      compare !== null
        ? t("rv_implied_roe", { implied: value, roe: compare })
        : t("rv_implied_roe_nocompare", { implied: value });
  } else {
    sentence =
      compare !== null
        ? t("rv_implied_growth", { implied: value, years: STAGE_ONE_YEARS, cap: compare })
        : t("rv_implied_growth_nocap", { implied: value, years: STAGE_ONE_YEARS });
  }

  return (
    <div className="rs-implied">
      <span className="rs-implied-label">{t("rv_implied_label")}</span>
      <div className="rs-sentence">
        {sentence}
        <InfoPopover label={t("rv_implied_info_label")}>
          <p>{t(isRoe ? "rv_implied_info_roe" : "rv_implied_info_growth")}</p>
        </InfoPopover>
      </div>
    </div>
  );
}
