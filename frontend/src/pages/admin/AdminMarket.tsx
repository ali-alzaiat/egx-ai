import "../shared/fields.css";
import "./Admin.css";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { startMarketRefresh, useSyncStatus } from "../../api/client";
import { Missing } from "../../components/ui/Missing";
import { StatStrip, type StatItem } from "../../components/ui/StatStrip";
import { useLang } from "../../i18n/useLang";
import { fmtInt } from "../../lib/format";
import type { CopyKey } from "../../i18n";
import type { SyncJobStatus } from "../../types";
import { describeError } from "../shared/apiError";
import { ForeignText } from "../shared/ForeignText";
import { ErrorMessage, FormMessage } from "../shared/FormMessage";
import { fmtDateTime } from "../tracking/dateTime";
import type { ErrorView } from "../shared/apiError";

// Query families that depend on market data; invalidated when a refresh finishes.
const REFRESH_KEYS = [
  ["dataQuality"],
  ["signals"],
  ["stance"],
  ["prices"],
  ["latestPrice"],
  ["dataSources"],
] as const;

const STATE_KEY: Record<SyncJobStatus["status"], CopyKey> = {
  idle: "adm_sync_idle",
  accepted: "adm_sync_running",
  running: "adm_sync_running",
  done: "adm_sync_done",
  partial: "adm_sync_partial",
  failed: "adm_sync_failed",
};

/**
 * Market data admin: "Refresh market data" moved here from the company
 * Overview (R43 #14). The job is polled through useSyncStatus; a 409 adopts
 * the live job.
 */
export default function AdminMarket() {
  const { t, locale } = useLang();
  const queryClient = useQueryClient();
  const syncQuery = useSyncStatus();
  const job = syncQuery.data;
  const live = job?.status === "accepted" || job?.status === "running";
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<ErrorView | null>(null);

  const statusLine = (j: SyncJobStatus | undefined): string => {
    if (!j || j.status === "idle" || j.status === "accepted") return t("admin_refreshing");
    switch (j.phase) {
      case "universe":
        return t("admin_refresh_universe");
      case "prices":
        return j.progress
          ? t("admin_refresh_prices", {
              done: fmtInt(locale, j.progress.completed) ?? "",
              total: fmtInt(locale, j.progress.total) ?? "",
            })
          : t("admin_refresh_prices_plain");
      case "assessment":
        return t("admin_refresh_assessment");
      default:
        return t("admin_refreshing");
    }
  };

  useEffect(() => {
    if (!refreshing) return;
    const status = job?.status;
    if (status !== "done" && status !== "partial" && status !== "failed") return;
    for (const key of REFRESH_KEYS) {
      void queryClient.invalidateQueries({ queryKey: [...key] });
    }
    if (status === "failed") {
      setError({ text: t("admin_refresh_failed"), detail: job?.error ?? null });
    } else {
      let msg = t("admin_refresh_done", {
        records: fmtInt(locale, job?.prices?.records_written ?? 0) ?? "",
        scores: fmtInt(locale, job?.assessment?.scores_written ?? 0) ?? "",
      });
      if (status === "partial") {
        msg += ` ${t("admin_refresh_partial", { count: fmtInt(locale, job?.prices?.failed_count ?? 0) ?? "" })}`;
      }
      setMessage(msg);
    }
    setRefreshing(false);
  }, [refreshing, job, queryClient, t, locale]);

  const onRefresh = async (): Promise<void> => {
    setRefreshing(true);
    setError(null);
    setMessage(null);
    try {
      await startMarketRefresh();
      await syncQuery.refetch();
    } catch (err) {
      setRefreshing(false);
      setError(describeError(err, t, "admin_refresh_failed"));
    }
  };

  const ran = !!job && job.status !== "idle";
  const failures = job?.prices?.failed_tickers ?? [];
  const failedCount = job?.prices?.failed_count ?? 0;
  const summary: StatItem[] = [
    { id: "state", label: t("adm_sync_state"), value: job ? t(STATE_KEY[job.status]) : <Missing /> },
    {
      id: "finished",
      label: t("adm_sync_finished"),
      numeric: true,
      value: ran ? (fmtDateTime(locale, job.finished_at) ?? <Missing localized={t("adm_sync_unfinished")} />) : <Missing localized={t("adm_sync_never")} />,
    },
    {
      id: "records",
      label: t("adm_sync_records"),
      numeric: true,
      value: job?.prices ? fmtInt(locale, job.prices.records_written) : <Missing localized={t("adm_sync_never")} />,
    },
    {
      id: "failed",
      label: t("adm_sync_failed_count"),
      numeric: true,
      value: job?.prices ? fmtInt(locale, failedCount) : <Missing localized={t("adm_sync_never")} />,
    },
  ];

  return (
    <section className="page">
      <p>{t("admin_market_intro")}</p>
      <StatStrip items={summary} label={t("adm_sync_summary")} />
      <div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => void onRefresh()}
          disabled={refreshing || live}
        >
          {refreshing || live ? t("admin_refreshing") : t("admin_refresh")}
        </button>
      </div>
      {(refreshing || live) && (
        <p role="status" className="muted">
          {statusLine(job)}
        </p>
      )}
      {message && <FormMessage kind="success" text={message} />}
      {error && <ErrorMessage view={error} />}
      {failures.length > 0 && (
        <details className="fold">
          <summary>{t("adm_sync_failures", { count: fmtInt(locale, failedCount) ?? "" })}</summary>
          <ul className="adm-failures">
            {failures.map((f) => (
              <li key={f.ticker}>
                <bdi dir="ltr">{f.ticker}</bdi>: <ForeignText>{f.error}</ForeignText>
              </li>
            ))}
          </ul>
          {failedCount > failures.length && (
            <p className="muted">{t("adm_sync_more", { count: fmtInt(locale, failedCount - failures.length) ?? "" })}</p>
          )}
        </details>
      )}
    </section>
  );
}
