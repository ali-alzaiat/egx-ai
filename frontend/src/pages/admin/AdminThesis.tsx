import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { updateThesis, useThesis } from "../../api/client";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States";
import { useLang } from "../../i18n/useLang";
import { fmtDate } from "../../lib/format";
import type { Company, ThesisAssessment } from "../../types";
import { describeError, type ErrorView } from "../shared/apiError";
import { Field } from "../shared/Field";
import { ErrorMessage, FormMessage } from "../shared/FormMessage";
import { ForeignText } from "../shared/ForeignText";
import { humanizeCode } from "../shared/humanize";
import {
  CATALYST_OUTCOMES,
  CLASSIFICATION_KEY,
  INVALIDATION_KEY,
  INVALIDATION_STATUSES,
  LEDGER_CLASSIFICATIONS,
  OUTCOME_KEY,
  changedCatalysts,
  changedInvalidations,
  enumLabel,
} from "./adminFormat";

/** The documented update form: a rationale is required; only changed rows are sent. */
function UpdateForm({
  companyId,
  assessment,
  onDone,
}: {
  companyId: string;
  assessment: ThesisAssessment;
  onDone: () => Promise<void>;
}) {
  const { t } = useLang();
  const [rationale, setRationale] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [classification, setClassification] = useState<string>("Pending");
  const [statuses, setStatuses] = useState<Record<string, string>>({});
  const [outcomes, setOutcomes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorView | null>(null);
  const [saved, setSaved] = useState(false);

  const blank = rationale.trim() === "";

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (blank) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const invalidations = changedInvalidations(assessment.invalidations, statuses);
      const catalysts = changedCatalysts(assessment.catalysts, outcomes);
      await updateThesis(companyId, {
        rationale: rationale.trim(),
        ...(reviewer.trim() === "" ? {} : { reviewer: reviewer.trim() }),
        classification,
        ...(invalidations.length > 0 ? { invalidations } : {}),
        ...(catalysts.length > 0 ? { catalysts } : {}),
      });
      setRationale("");
      setReviewer("");
      setStatuses({});
      setOutcomes({});
      await onDone();
      setSaved(true);
    } catch (err) {
      setError(describeError(err, t, "adm_thesis_failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card panel" onSubmit={(e) => void submit(e)}>
      <h3>{t("adm_update_title")}</h3>
      <p className="panel-lead">{t("adm_update_lead")}</p>
      <Field label={t("adm_rationale")}>
        <textarea rows={4} value={rationale} onChange={(e) => setRationale(e.target.value)} />
      </Field>
      <div className="fld-row">
        <Field label={t("adm_reviewer")}>
          <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
        </Field>
        <Field label={t("adm_classification")}>
          <select value={classification} onChange={(e) => setClassification(e.target.value)}>
            {LEDGER_CLASSIFICATIONS.map((c) => (
              <option key={c} value={c}>
                {enumLabel(c, CLASSIFICATION_KEY, t)}
              </option>
            ))}
          </select>
        </Field>
      </div>

      {assessment.invalidations.length > 0 && (
        <fieldset className="fld-fieldset">
          <legend>{t("adm_invalidations")}</legend>
          {assessment.invalidations.map((inv) => (
            <Field
              key={inv.metric}
              label={
                <ForeignText>{humanizeCode(inv.metric)}</ForeignText>
              }
              hint={t("adm_now", { value: enumLabel(inv.status, INVALIDATION_KEY, t) })}
            >
              <select
                value={statuses[inv.metric] ?? inv.status}
                onChange={(e) => setStatuses((prev) => ({ ...prev, [inv.metric]: e.target.value }))}
              >
                {INVALIDATION_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {enumLabel(s, INVALIDATION_KEY, t)}
                  </option>
                ))}
              </select>
            </Field>
          ))}
        </fieldset>
      )}

      {assessment.catalysts.length > 0 && (
        <fieldset className="fld-fieldset">
          <legend>{t("adm_catalysts")}</legend>
          {assessment.catalysts.map((c) => (
            <Field
              key={c.id}
              label={<ForeignText>{c.event}</ForeignText>}
              hint={t("adm_now", { value: enumLabel(c.outcome, OUTCOME_KEY, t) })}
            >
              <select
                value={outcomes[c.id] ?? c.outcome}
                onChange={(e) => setOutcomes((prev) => ({ ...prev, [c.id]: e.target.value }))}
              >
                {CATALYST_OUTCOMES.map((o) => (
                  <option key={o} value={o}>
                    {enumLabel(o, OUTCOME_KEY, t)}
                  </option>
                ))}
              </select>
            </Field>
          ))}
        </fieldset>
      )}

      {error && <ErrorMessage view={error} />}
      {saved && <FormMessage kind="success" text={t("adm_saved")} />}
      <div>
        <button type="submit" className="btn btn-primary" disabled={busy || blank}>
          {busy ? t("adm_saving") : t("adm_record_update")}
        </button>
        {blank && <p className="fld-hint">{t("adm_rationale_first")}</p>}
      </div>
    </form>
  );
}

/** Read-only, oldest-first ledger of documented updates. */
function Ledger({ assessment }: { assessment: ThesisAssessment }) {
  const { t, locale } = useLang();
  const rows = assessment.ledger;
  return (
    <section className="adm-stack" aria-label={t("adm_ledger")}>
      <h2 className="section-title">{t("adm_ledger")}</h2>
      <p className="muted">{t("adm_ledger_lead")}</p>
      {rows.length === 0 ? (
        <EmptyState>{t("adm_ledger_empty")}</EmptyState>
      ) : (
        <ol className="adm-ledger">
          {rows.map((row, i) => (
            <li key={`${row.created_at ?? "none"}-${i}`} className="card">
              <p>
                <strong>{enumLabel(row.classification, CLASSIFICATION_KEY, t)}</strong>
              </p>
              <p>
                <ForeignText>{row.rationale}</ForeignText>
              </p>
              <p className="text-note">
                {row.reviewer ?? t("adm_no_reviewer")} · {fmtDate(locale, row.created_at) ?? t("no_value")} ·{" "}
                {t("al_methodology")} <bdi dir="ltr">v{row.methodology_version}</bdi>
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/** Documented thesis update for one company, with the read-only ledger below. */
export default function AdminThesis({ company }: { company: Company }) {
  const { t } = useLang();
  const queryClient = useQueryClient();
  const thesis = useThesis(company.id);

  if (thesis.isLoading) return <LoadingState thing={t("adm_things_thesis")} />;
  if (thesis.isError) return <ErrorState thing={t("adm_things_thesis")} onRetry={() => void thesis.refetch()} />;

  const assessment = thesis.data?.assessment ?? null;
  if (!assessment) return <EmptyState>{t("adm_thesis_none", { ticker: company.ticker })}</EmptyState>;

  return (
    <div className="adm-stack">
      <UpdateForm
        companyId={company.id}
        assessment={assessment}
        onDone={async () => {
          await queryClient.invalidateQueries({ queryKey: ["thesis"] });
        }}
      />
      <Ledger assessment={assessment} />
    </div>
  );
}
