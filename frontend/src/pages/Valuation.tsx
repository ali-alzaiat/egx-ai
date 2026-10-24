import { useParams } from "react-router-dom";
import { useCompanyByTicker, useFairValue } from "../api/client";
import FairValueCard from "../components/FairValueCard";
import SensitivityTable from "../components/SensitivityTable";
import AssumptionsTable from "../components/research/AssumptionsTable";
import { TechnicalDetails } from "../components/research/parts";
import { Reason } from "../components/research/reasons";
import { Notice } from "../components/ui/Notice";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import { fmtDate } from "../lib/format";

/**
 * Valuation tab (R43 #1): the weighted fair value is computed on read from
 * stored statement lines and sourced assumptions. Nothing here is typed in; the
 * estimate holds only under the stated methodology and assumptions.
 */
export default function Valuation() {
  const { ticker } = useParams<{ ticker: string }>();
  const { t, locale } = useLang();
  const { data: company } = useCompanyByTicker(ticker);
  const { data: fairValue, isLoading, error, refetch } = useFairValue(company?.id);

  if (!company || isLoading) return <LoadingState thing={t("rv_thing")} />;
  if (error) return <ErrorState thing={t("rv_thing")} onRetry={() => void refetch()} />;
  if (!fairValue) return <EmptyState>{t("rv_empty", { ticker: company.ticker })}</EmptyState>;

  const asOf = fmtDate(locale, fairValue.as_of);
  const sources = Object.entries(fairValue.input_sources).filter(([, v]) => v !== null && v !== "");
  const inputs = Object.entries(fairValue.inputs).filter(([, v]) => v !== null && v !== "");

  return (
    <div className="page">
      {fairValue.compute_status === "failed" && (
        <Notice variant="warning">
          {t("rs_compute_failed")}
          {fairValue.compute_error && (
            <>
              {" "}
              <Reason reason={fairValue.compute_error} />
            </>
          )}
        </Notice>
      )}

      <FairValueCard fairValue={fairValue} />
      <AssumptionsTable fairValue={fairValue} />
      <SensitivityTable rows={fairValue.sensitivity} baseValue={fairValue.fair_value.value} />

      <footer className="rs-stack">
        <p className="rs-note">
          {t("rv_footer", {
            version: fairValue.methodology_version,
            asof: asOf !== null ? t("rs_as_of", { date: asOf }) : t("rs_no_data_reason"),
          })}
          {" · "}
          {t("rs_research_note")}
        </p>
        <TechnicalDetails>
          <span>{`profile = ${fairValue.profile.profile_id}`}</span>
          <span>{`primary_model = ${fairValue.profile.primary_model}`}</span>
          <span>{`fallback_model = ${fairValue.profile.fallback_model}`}</span>
          {inputs.map(([key, value]) => (
            <span key={`in-${key}`}>{`${key} = ${String(value)}`}</span>
          ))}
          {sources.map(([key, value]) => (
            <span key={`src-${key}`}>{`${key} <- ${String(value)}`}</span>
          ))}
        </TechnicalDetails>
      </footer>
    </div>
  );
}
