import type { UseQueryResult } from "@tanstack/react-query";
import { useLang } from "../../i18n/useLang";
import { fmtDate, fmtInt, fmtPct, fmtPrice } from "../../lib/format";
import { calibrationAvailable, horizonLabel } from "../../lib/priceOverlays";
import type { ConeCalibration, ConeHorizon, VolatilityConeResponse } from "../../types";
import { BackendText } from "../ui/BackendText";
import { ErrorState, LoadingState } from "../ui/States";

function range(locale: string, low: string, high: string): string {
  return `${fmtPrice(locale, low) ?? "—"} – ${fmtPrice(locale, high) ?? "—"}`;
}

function Horizons({ horizons }: { horizons: readonly ConeHorizon[] }) {
  const { t, locale } = useLang();
  return (
    <ul className="price-cal" aria-label={t("pxf_cone_title")}>
      {horizons.map((h) => (
        <li key={h.days} className="price-cal-item">
          <p className="price-cal-head">
            {t("pxf_cone_horizon", { horizon: horizonLabel(t, h.days), date: fmtDate(locale, h.approx_date) ?? "" })}
          </p>
          <dl>
            <div className="price-cal-row">
              <dt>{t("pxf_cone_range_50")}</dt>
              <dd dir="ltr">{range(locale, h.p25, h.p75)}</dd>
            </div>
            <div className="price-cal-row">
              <dt>{t("pxf_cone_range_90")}</dt>
              <dd dir="ltr">{range(locale, h.p05, h.p95)}</dd>
            </div>
          </dl>
        </li>
      ))}
    </ul>
  );
}

function Calibration({ calibration }: { calibration: ConeCalibration }) {
  const { t, locale } = useLang();
  const share = (v: number, low: number, high: number): string =>
    t("pxf_cal_share", { share: fmtPct(locale, v) ?? "—", low: fmtPct(locale, low) ?? "—", high: fmtPct(locale, high) ?? "—" });
  return (
    <section className="price-cal-section" aria-label={t("pxf_cal_title")}>
      <h4 className="price-panel-title">{t("pxf_cal_title")}</h4>
      <p className="price-panel-note">{t("pxf_cal_intro")}</p>
      <ul className="price-cal">
        {calibration.horizons.map((h) => (
          <li key={h.days} className="price-cal-item">
            <p className="price-cal-head">{horizonLabel(t, h.days)}</p>
            {calibrationAvailable(h) ? (
              <>
                <dl>
                  <div className="price-cal-row">
                    <dt>{t("pxf_cal_inside_50")}</dt>
                    <dd dir="ltr">{share(h.inside_50, h.inside_50_low, h.inside_50_high)}</dd>
                  </div>
                  <div className="price-cal-row">
                    <dt>{t("pxf_cal_inside_90")}</dt>
                    <dd dir="ltr">{share(h.inside_90, h.inside_90_low, h.inside_90_high)}</dd>
                  </div>
                </dl>
                <p className="price-cal-detail">
                  {t("pxf_cal_cases", {
                    n: fmtInt(locale, h.n_cases) ?? "",
                    first: fmtDate(locale, h.first_case) ?? "",
                    last: fmtDate(locale, h.last_case) ?? "",
                  })}
                </p>
              </>
            ) : (
              <p className="price-cal-detail">
                {t("pxf_cal_not_measured")}{" "}
                <BackendText>{h.reason ?? ""}</BackendText>
              </p>
            )}
          </li>
        ))}
      </ul>
      <p className="price-panel-note">
        {t("pxf_cal_overlap_note")}
      </p>
    </section>
  );
}

/**
 * The volatility cone beside the chart: the numbers behind the bands and, per
 * horizon, the measured share of past cases that ended inside them (R47 P3/P5).
 * A range of typical moves, never a prediction: no point forecast, no trend.
 */
export default function ConePanel({ query }: { query: UseQueryResult<VolatilityConeResponse> }) {
  const { t, locale } = useLang();
  const cone = query.data;

  return (
    <section className="price-panel card-surface" aria-label={t("pxf_cone_title")}>
      <h3 className="price-panel-title">{t("pxf_cone_title")}</h3>
      {query.isLoading ? (
        <LoadingState thing={t("pxf_cone_title")} />
      ) : query.error || !cone ? (
        <ErrorState thing={t("pxf_cone_title")} onRetry={() => void query.refetch()} />
      ) : cone.status !== "AVAILABLE" ? (
        <>
          <p className="empty">{t("pxf_cone_unavailable")}</p>
          {cone.reason && (
            <p className="price-panel-note">
              <BackendText>{cone.reason}</BackendText>
            </p>
          )}
          <Calibration calibration={cone.calibration} />
        </>
      ) : (
        <>
          <p className="price-panel-note">
            {t("pxf_cone_intro", {
              price: fmtPrice(locale, cone.last_close) ?? "",
              n: fmtInt(locale, cone.n_returns) ?? "",
              sigma: fmtPct(locale, cone.sigma_annual) ?? "—",
            })}
          </p>
          <Horizons horizons={cone.horizons} />
          <p className="price-panel-note">
            {t("pxf_cone_note")}
          </p>
          <p className="price-panel-note">
            {t("pxf_cone_calendar_note")}
          </p>
          <Calibration calibration={cone.calibration} />
        </>
      )}
    </section>
  );
}
