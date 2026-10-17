import "./Events.css";

import { memo, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { exportEvents, getCompanyByTicker, useCompanies, useEvents } from "../api/client";
import type { PhaseEvent } from "../types";

interface EventFilters {
  symbol: string;
  type: string;
  date_from: string;
  date_to: string;
}

const EMPTY_FILTERS: EventFilters = { symbol: "", type: "", date_from: "", date_to: "" };

const EVENT_TYPES = [
  "watchlist.add",
  "watchlist.remove",
  "alert.created",
  "alert.fired",
  "alert.acked",
  "fact.landed",
  "check.evaluated",
  "restatement.detected",
  "thesis.updated",
  "rule.changed",
  "note.added",
] as const;

function prettifyEventType(type: string): string {
  const [a, b] = type.split(".");
  if (!a || !b) return type;
  const cap = (s: string): string => s.charAt(0).toUpperCase() + s.slice(1);
  return `${cap(a)} ${b}`;
}

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

const EventRow = memo(function EventRow({
  event,
  companyName,
}: {
  event: PhaseEvent;
  companyName: (id: string) => { ticker: string; name: string } | null;
}) {
  const highlights = useMemo(
    () => snapshotHighlights(event.inputs_snapshot ?? {}),
    [event.inputs_snapshot],
  );
  const actorRole = event.actor_type === "system" ? "by the system" : "by you";
  return (
    <article className="events-row" id={`event-${event.id}`} aria-label={`Event ${event.id}`}>
      <div className="events-row-head">
        <span className="events-type" title={`Rule version ${event.rule_version}`}>
          {prettifyEventType(event.type)}
        </span>
        <span className="muted">{formatTs(event.ts)}</span>
      </div>
      <p className="events-reason">{event.reason || "No reason recorded."}</p>
      <p className="muted">
        {event.symbols.length > 0 ? (
          <>
            {event.symbols.map((s) => {
              const found = companyName(s);
              return found ? (
                <span key={s}>
                  <Link to={`/companies/${found.ticker}`}>{found.ticker}</Link>
                  <span className="muted"> — {found.name}; </span>
                </span>
              ) : (
                <span key={s} className="events-symbol" title={s}>
                  {s.slice(0, 8)}…
                </span>
              );
            })}
          </>
        ) : (
          "No company attached"
        )}
      </p>
      {highlights.length > 0 && <p className="muted">Inputs: {highlights.join(" · ")}</p>}
      <details className="events-details">
        <summary>Technical details</summary>
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
        Validate or invalidate under these assumptions — this record is evidence, not advice.{" "}
        <span title={`Actor ${event.actor_type} ${event.actor_id}`}>
          Recorded {actorRole}.
        </span>
      </p>
    </article>
  );
});

export default function Events() {
  const [draft, setDraft] = useState<EventFilters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<EventFilters>(EMPTY_FILTERS);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [filterError, setFilterError] = useState<string | null>(null);

  const { data: companiesPage1 } = useCompanies({ page_size: 200 });
  const { data: companiesPage2 } = useCompanies({ page_size: 200, page: 2 });

  const companyOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const page of [companiesPage1, companiesPage2]) {
      for (const c of page?.items ?? []) {
        if (!seen.has(c.ticker)) seen.set(c.ticker, c.name);
      }
    }
    return [...seen.entries()]
      .map(([ticker, name]) => ({ ticker, name }))
      .sort((a, b) => a.ticker.localeCompare(b.ticker));
  }, [companiesPage1, companiesPage2]);
  const companiesLoading = companiesPage1 === undefined && companiesPage2 === undefined;

  // Ticker shown in the UI; the backend symbol filter takes a company UUID.
  const [symbolTicker, setSymbolTicker] = useState("");

  const handleApply = async (): Promise<void> => {
    setFilterError(null);
    const next = { ...draft, symbol: "" };
    const rawTicker = symbolTicker.trim().toUpperCase();
    if (rawTicker !== "") {
      let company = null;
      try {
        company = await getCompanyByTicker(rawTicker);
      } catch (err) {
        setFilterError(err instanceof Error ? err.message : "Could not look up that ticker.");
        return;
      }
      if (!company) {
        setFilterError(`No company "${rawTicker}" — pick one from the list.`);
        return;
      }
      next.symbol = company.id;
    }
    setApplied(next);
  };

  const params = useMemo(() => toQueryParams(applied), [applied]);
  const { data, isLoading, error, refetch } = useEvents(params);

  const events = useMemo(() => [...(data ?? [])].sort((a, b) => b.ts.localeCompare(a.ts)), [data]);

  const companyById = useMemo(() => {
    const byId = new Map<string, { ticker: string; name: string }>();
    for (const page of [companiesPage1, companiesPage2]) {
      for (const c of page?.items ?? []) {
        if (!byId.has(c.id)) byId.set(c.id, { ticker: c.ticker, name: c.name });
      }
    }
    return byId;
  }, [companiesPage1, companiesPage2]);

  const companyName = (id: string): { ticker: string; name: string } | null =>
    companyById.get(id) ?? null;

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
          void handleApply();
        }}
      >
        <label>
          Symbol / company
          <select
            value={symbolTicker}
            onChange={(e) => setSymbolTicker(e.target.value)}
            disabled={companiesLoading}
          >
            <option value="">All companies</option>
            {companyOptions.map((c) => (
              <option key={c.ticker} value={c.ticker}>
                {c.ticker} — {c.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Event type
          <select
            value={draft.type}
            onChange={(e) => setDraft((d) => ({ ...d, type: e.target.value }))}
          >
            <option value="">All types</option>
            {EVENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {prettifyEventType(t)}
              </option>
            ))}
          </select>
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
              setSymbolTicker("");
              setFilterError(null);
            }}
          >
            Clear
          </button>
        </div>
        {filterError ? (
          <div className="alert alert-error" role="alert">
            {filterError}{" "}
            <button
              type="button"
              className="link-btn"
              onClick={() => {
                setSymbolTicker("");
                void handleApply();
              }}
            >
              Show all companies
            </button>
          </div>
        ) : null}
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
        <div className="alert alert-error" role="alert">
          Couldn&apos;t load events. Check the symbol field — use a ticker from the list.{" "}
          <button className="link-btn" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      ) : events.length === 0 ? (
        applied.symbol === "" &&
        applied.type === "" &&
        applied.date_from === "" &&
        applied.date_to === "" ? (
          <div className="empty">
            No events yet. Assess a company or fire an alert to start the ledger.
          </div>
        ) : (
          <div className="empty">
            No events for these filters.{" "}
            <button
              className="link-btn"
              onClick={() => {
                setDraft(EMPTY_FILTERS);
                setApplied(EMPTY_FILTERS);
                setSymbolTicker("");
              }}
            >
              Clear filters
            </button>
          </div>
        )
      ) : (
        <div className="events-feed">
          {events.map((event) => (
            <EventRow key={event.id} event={event} companyName={companyName} />
          ))}
        </div>
      )}
    </div>
  );
}
