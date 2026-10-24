import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { startMarketRefresh, useSyncStatus } from "../../api/client";
import { Notice } from "../../components/ui/Notice";
import { useLang } from "../../i18n/useLang";
import type { SyncJobStatus } from "../../types";

// Query families that depend on market data; invalidated when a refresh finishes.
const REFRESH_KEYS = [
  ["dataQuality"],
  ["signals"],
  ["stance"],
  ["prices"],
  ["latestPrice"],
  ["dataSources"],
] as const;

/**
 * Market data admin: "Refresh market data" moved here from the company
 * Overview (spec 1.4). The job is polled through useSyncStatus; a 409 adopts
 * the live job.
 */
export default function AdminMarket() {
  const { t } = useLang();
  const queryClient = useQueryClient();
  const syncQuery = useSyncStatus();
  const job = syncQuery.data;
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);

  const statusLine = (j: SyncJobStatus | undefined): string => {
    if (!j || j.status === "idle" || j.status === "accepted") return t("admin_refreshing");
    switch (j.phase) {
      case "universe":
        return t("admin_refresh_universe");
      case "prices":
        return j.progress
          ? t("admin_refresh_prices", { done: j.progress.completed, total: j.progress.total })
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
      setErrorText(t("admin_refresh_failed", { error: job?.error ?? t("admin_refresh_unknown_error") }));
    } else {
      let msg = t("admin_refresh_done", {
        records: job?.prices?.records_written ?? 0,
        scores: job?.assessment?.scores_written ?? 0,
      });
      if (status === "partial") {
        msg += ` ${t("admin_refresh_partial", { count: job?.prices?.failed_count ?? 0 })}`;
        console.warn("Market refresh partial failure:", job?.prices?.failed_tickers);
      }
      setMessage(msg);
    }
    setRefreshing(false);
  }, [refreshing, job, queryClient, t]);

  const onRefresh = async (): Promise<void> => {
    setRefreshing(true);
    setErrorText(null);
    setMessage(null);
    try {
      await startMarketRefresh();
      await syncQuery.refetch();
    } catch (err) {
      setRefreshing(false);
      setErrorText(
        t("admin_refresh_failed", { error: err instanceof Error ? err.message : t("admin_refresh_unknown_error") }),
      );
    }
  };

  return (
    <section className="page">
      <p>{t("admin_market_intro")}</p>
      <div>
        <button type="button" className="btn btn-primary" onClick={() => void onRefresh()} disabled={refreshing}>
          {refreshing ? t("admin_refreshing") : t("admin_refresh")}
        </button>
      </div>
      {refreshing && (
        <p role="status" className="muted">
          {statusLine(job)}
        </p>
      )}
      {message && (
        <p role="status" className="muted">
          {message}
        </p>
      )}
      {errorText && <Notice variant="warning">{errorText}</Notice>}
    </section>
  );
}
