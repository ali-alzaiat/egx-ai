import { Badge } from "@/components/shadcn/badge";
import { Button } from "@/components/shadcn/button";
import { useCrossChecks, useRunCrossChecks } from "../api/client";
import { useLang } from "../i18n/useLang";
import { describeCheck } from "../lib/crosscheckView";
import { crossCheckNameKey, crossCheckStatus, evidenceRows } from "../lib/crosschecks";
import { fmtDateTime } from "../lib/format";
import type { CrossCheck } from "../types";
import { ExplainButton } from "./assistant/ExplainButton";
import { BackendText } from "./ui/BackendText";
import { EmptyState, ErrorState, LoadingState } from "./ui/States";

function StatusPill({ status }: { status: string }) {
  const { t } = useLang();
  const { tone, key } = crossCheckStatus(status);
  // The word is the signal; the colour only backs it up.
  return <Badge variant={tone}>{t(key)}</Badge>;
}

function CheckRow({ check }: { check: CrossCheck }) {
  const { t, locale } = useLang();
  const nameKey = crossCheckNameKey(check.code);
  // Known checks read as translated sentences and labels; an unknown check shows the backend's wording and raw evidence.
  const view = describeCheck(check, locale, t);
  const rows = view ? view.rows : evidenceRows(check.evidence, check.code).map((r) => ({ label: r.key, value: r.value }));
  return (
    <li className="flex flex-col gap-2 border-b border-border py-3 last:border-b-0">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="min-w-0 flex-1 text-ui font-semibold">
          {nameKey ? t(nameKey) : <span dir="ltr">{check.code}</span>}
        </h3>
        <StatusPill status={check.status} />
      </div>
      <p className="text-ui text-text-2">{view ? view.summary : <BackendText>{check.detail}</BackendText>}</p>
      {rows.length > 0 && (
        <dl
          dir={view ? undefined : "ltr"}
          className="m-0 grid grid-cols-[minmax(0,max-content)_minmax(0,1fr)] gap-x-4 gap-y-1 text-meta"
        >
          {rows.map((row) => (
            <div key={row.label} className="contents">
              <dt className="break-words text-muted-foreground">{row.label}</dt>
              <dd className="m-0 break-words text-foreground">{row.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </li>
  );
}

/** Quality tab, top section (R50): the latest data cross-checks with a button to run them now. */
export default function CrossChecksSection({ companyId, ticker }: { companyId: string; ticker: string }) {
  const { t, locale } = useLang();
  const { data, isLoading, error, refetch } = useCrossChecks(companyId);
  const run = useRunCrossChecks(companyId);
  const title = t("xc_title");

  if (isLoading) return <LoadingState thing={title} />;
  if (error || !data) return <ErrorState thing={title} onRetry={() => void refetch()} />;

  const never = data.computed_at === null || data.checks.length === 0;
  const computed = fmtDateTime(locale, data.computed_at);

  return (
    <section className="card-surface flex min-w-0 flex-col gap-3" aria-labelledby="xc-title">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="xc-title" className="section-title mb-0 min-w-0 flex-1">
          {title}
        </h2>
        {!never && data.overall !== null && (
          <span className="flex items-center gap-2 text-ui text-text-2">
            {t("xc_overall")}
            <StatusPill status={data.overall} />
          </span>
        )}
      </div>
      <p className="text-ui text-text-2">{t("xc_intro")}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => run.mutate()} disabled={run.isPending}>
          {run.isPending ? t("xc_running") : t("xc_run")}
        </Button>
        <ExplainButton card="data_check" ticker={ticker} />
      </div>
      {run.isError && (
        <p role="alert" className="text-ui text-loss">
          {t("xc_run_failed")}
        </p>
      )}
      {never ? (
        <EmptyState>{t("xc_empty")}</EmptyState>
      ) : (
        <>
          <ul className="m-0 flex list-none flex-col p-0">
            {data.checks.map((check) => (
              <CheckRow key={check.code} check={check} />
            ))}
          </ul>
          <p className="text-meta text-muted-foreground">
            {t("xc_footnote", {
              version: data.methodology_version ?? "—",
              time: computed ?? "—",
            })}
          </p>
        </>
      )}
    </section>
  );
}
