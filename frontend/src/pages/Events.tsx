import "./Events.css";

import { memo, useMemo, useState } from "react";
import { exportEvents, useEvents } from "../api/client";
import type { PhaseEvent } from "../types";

interface EventFilters {
  symbol: string;
  type: string;
  date_from: string;
  date_to: string;
}

const EMPTY_FILTERS: EventFilters = { symbol: "", type: "", date_from: "", date_to: "" };

function toQueryParams(filters: EventFilters): {
  symbol?: string;
  type?: string;
  date_from?: string;
  date_to?: string;
} {
  const params: { symbol?: string; type?: string; date_from?: string; date_to?: string } = {};
  const symbol = filters.symbol.trim().toUpperCase();
  if (symbol) params.symbol = symbol;
  if (filters.type) params.type = filters.type;
  if (filters.date_from) params.date_from = filters.date_from;
  if (filters.date_to) params.date_to = filters.date_to;
  return params;
}

function formatTs(ts: string): string {
  const t = new Date(ts).getTime();
  if (Number.isNaN(t)) return ts;
  return new Date(ts).toLocaleString();
}

/** Pull the well-known provenance keys out of an opaque inputs snapshot. */
function snapshotHighlights(snapshot: Record<string, unknown>): string[] {
  const out: string[] = [];
  const facts = snapshot.fact_ids ?? snapshot.facts ?? snapshot.factIds;
  if (Array.isArray(facts) && facts.length > 0) out.push(`fact ids: ${facts.map(String).join(", ")}`);
  const priceAsOf = snapshot.price_as_of ?? snapshot.priceAsOf;
  if (typeof priceAsOf === "string" && priceAsOf) out.push(`price as-of: ${priceAsOf}`);
  const methodology = snapshot.methodology_version ?? snapshot.methodologyVersion;
  if (typeof methodology === "string" && methodology) out.push(`methodology v${methodology}`);
  return out;
}

function stringifySnapshot(snapshot: Record<string, unknown>): string {
  try {
    return JSON.stringify(snapshot, null, 2);
  } catch {
    return String(snapshot);
  }
}

const EventRow = memo(function EventRow({ event }: { event: PhaseEvent }) {
  const highlights = useMemo(
    () => snapshotHighlights(event.inputs_snapshot ?? {}),
    [event.inputs_snapshot],
  );
  return (
    <article className="events-row" id={`event-${event.id}`} aria-label={`Event ${event.id}`}>
      <div className="events-row-head">
        <span className="events-type" title={`Rule version ${event.rule_version}`}>
          {event.type}
        </span>
        <span className="muted">{formatTs(event.ts)}</span>
      </div>
      <p className="events-reason">{event.reason || "No reason recorded."}</p>
      <p className="muted">
        Actor: {event.actor_type}
        {event.actor_id ? ` · ${event.actor_id}` : ""} · methodology v{event.rule_version}
        {event.symbols.length > 0 ? (
          <>
            {" · "}
            {event.symbols.map((s) => (
              <span key={s} className="events-symbol">
                {s}
              </span>
            ))}
          </>
        ) : (
          " · no symbols"
        )}
      </p>
      {highlights.length > 0 && <p className="muted">Inputs: {highlights.join(" · ")}</p>}
      <details className="events-details">
        <summary>Inputs snapshot</summary>
        <pre>{stringifySnapshot(event.inputs_snapshot ?? {})}</pre>
      </details>
      {event.supersedes_id ? (
        <p className="muted">
          Corrects{" "}
          <a href={`#event-${event.supersedes_id}`}>
            {event.supersedes_id.slice(0, 8)}
          </a>{" "}
          — corrections arrive as new rows; the original is never edited.
        </p>
      ) : null}
      <p className="muted events-frame">
        Validate or invalidate under these assumptions — this record is evidence, not advice.
      </p>
    </article>
  );
});

export default function Events() {
  const [draft, setDraft] = useState<EventFilters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<EventFilters>(EMPTY_FILTERS);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const params = useMemo(() => toQueryParams(applied), [applied]);
  const { data, isLoading, error, refetch } = useEvents(params);

  const events = useMemo(() => [...(data ?? [])].sort((a, b) => b.ts.localeCompare(a.ts)), [data]);

  const handleExport = async (): Promise<void> => {
    setExporting(true);
    setExportError(null);
    try {
      const payload = await exportEvents(params);
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "events.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Events ledger</h1>
          <p className="subtitle">
            Append-only record of assessments, alerts, and corrections — newest first.
            Corrections appear as new rows referencing the old; nothing here is rewritten.
          </p>
        </div>
        <button className="btn btn-primary" onClick={handleExport} disabled={exporting}>
          {exporting ? "Exporting…" : "Export JSON"}
        </button>
      </div>

      <form
        className="card events-filters"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied(draft);
        }}
      >
        <label>
          Symbol / company
          <input
            type="text"
            value={draft.symbol}
            onChange={(e) => setDraft((d) => ({ ...d, symbol: e.target.value }))}
            placeholder="e.g. COMI"
          />
        </label>
        <label>
          Event type
          <input
            type="text"
            value={draft.type}
            onChange={(e) => setDraft((d) => ({ ...d, type: e.target.value }))}
            placeholder="e.g. score.assessed"
          />
        </label>
        <label>
          From
          <input
            type="date"
            value={draft.date_from}
            onChange={(e) => setDraft((d) => ({ ...d, date_from: e.target.value }))}
          />
        </label>
        <label>
          To
          <input
            type="date"
            value={draft.date_to}
            onChange={(e) => setDraft((d) => ({ ...d, date_to: e.target.value }))}
          />
        </label>
        <div className="events-filter-actions">
          <button type="submit" className="btn btn-primary">
            Apply filters
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => {
              setDraft(EMPTY_FILTERS);
              setApplied(EMPTY_FILTERS);
            }}
          >
            Clear
          </button>
        </div>
      </form>

      {exportError && (
        <div className="alert alert-error">
          Couldn&apos;t export events: {exportError}{" "}
          <button className="link-btn" onClick={handleExport}>
            Retry
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="loading">Loading events…</div>
      ) : error ? (
        <div className="alert alert-error">
          Couldn&apos;t load events.{" "}
          <button className="link-btn" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      ) : events.length === 0 ? (
        <div className="empty">No events recorded for these filters yet.</div>
      ) : (
        <div className="events-feed">
          {events.map((event) => (
            <EventRow key={event.id} event={event} />
          ))}
        </div>
      )}
    </div>
  );
}
