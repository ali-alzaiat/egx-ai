import "./Alerts.css";

import { memo, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  ackFiredAlert,
  createAlertRule,
  deleteAlertRule,
  getCompanyByTicker,
  updateAlertRule,
  useAlertRules,
  useCompanies,
  useFiredAlerts,
  useWatchlists,
} from "../api/client";
import { formatAsOf } from "../lib/format";
import type { AlertFired, AlertRule } from "../types";

const FAMILIES = ["price", "valuation_gap", "document", "score_change"] as const;
type AlertFamily = (typeof FAMILIES)[number];

const FAMILY_LABELS: Record<AlertFamily, string> = {
  price: "Price crossing",
  valuation_gap: "Valuation gap",
  document: "New document",
  score_change: "Score change",
};

const FAMILY_HINTS: Record<AlertFamily, string> = {
  price: "Fires when the latest price crosses the threshold in the chosen direction.",
  valuation_gap: "Fires when the gap between price and fair value reaches the given percent.",
  document: "Toggle-only: fires when a new filing lands for a company on the chosen list.",
  score_change: "Fires when the investment score moves by at least the given percent (a ±5% band counts as no change).",
};

function isFamily(value: string): value is AlertFamily {
  return (FAMILIES as readonly string[]).includes(value);
}

function stringifySnapshotValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function snapshotEntries(snapshot: Record<string, unknown>): [string, string][] {
  return Object.entries(snapshot).map(([key, value]) => [key, stringifySnapshotValue(value)]);
}

// Human summary of why a rule fired: the 2 facts that matter per family.
// The full snapshot stays behind a discreet Technical details fold.
function FiredSummary({ family, snapshot }: { family: string; snapshot: Record<string, unknown> }) {
  const str = (v: unknown): string => (v === null || v === undefined || v === "" ? "—" : String(v));
  if (family === "price") {
    return (
      <span>
        Crossed {str(snapshot.threshold)} {str(snapshot.direction ?? "above")} — observed{" "}
        {str(snapshot.current_close)}
        {typeof snapshot.price_as_of === "string" && snapshot.price_as_of
          ? ` as of ${formatAsOf(snapshot.price_as_of)}`
          : ""}
      </span>
    );
  }
  if (family === "valuation_gap") {
    return (
      <span>
        Gap {str(snapshot.gap_pct)}% — price {str(snapshot.current_close)} vs fair value{" "}
        {str(snapshot.fair_value)}
      </span>
    );
  }
  if (family === "score_change") {
    return (
      <span>
        Score moved {str(snapshot.change_pct)}% (band ±{str(snapshot.threshold_pct ?? 5)}% counts as
        no change) — {str(snapshot.previous_score)} → {str(snapshot.current_score)}
      </span>
    );
  }
  if (family === "document") {
    const ids = snapshot.fact_ids;
    const n = Array.isArray(ids) ? ids.length : 0;
    return (
      <span>
        {n > 0 ? `New filing landed (${n} parsed fact${n === 1 ? "" : "s"})` : "New filing landed"}
      </span>
    );
  }
  return <span>Fired — see technical details.</span>;
}

function ruleSummary(rule: AlertRule): string {
  const params = rule.params ?? {};
  switch (rule.family) {
    case "price":
      return `threshold ${stringifySnapshotValue(params.threshold)} (${stringifySnapshotValue(params.direction ?? "above")})`;
    case "valuation_gap":
      return `gap ≥ ${stringifySnapshotValue(params.gap_pct)}%`;
    case "score_change":
      return `move ≥ ${stringifySnapshotValue(params.threshold_pct)}% (±5% neutral band)`;
    case "document":
      return "any new filing";
    default:
      return Object.keys(params).length > 0 ? JSON.stringify(params) : "no parameters";
  }
}

function scopeLabel(
  rule: AlertRule,
  watchlistLink: (id: string | null) => ReactNode,
  companyLabel: (id: string | null) => ReactNode,
): ReactNode {
  if (rule.watchlist_id) {
    const link = watchlistLink(rule.watchlist_id);
    return link ? <span>List: {link}</span> : <span>List: unknown</span>;
  }
  if (rule.company_id) return companyLabel(rule.company_id);
  return "Whole universe";
}

interface RuleRowProps {
  rule: AlertRule;
  scope: ReactNode;
  pending: boolean;
  onToggle: (rule: AlertRule) => void;
  onDelete: (rule: AlertRule) => void;
}

const RuleRow = memo(function RuleRow({ rule, scope, pending, onToggle, onDelete }: RuleRowProps) {
  return (
    <li className={rule.enabled ? "alerts-rule" : "alerts-rule alerts-dimmed"}>
      <div>
        <strong>{FAMILY_LABELS[rule.family as AlertFamily] ?? rule.family}</strong>
        <span className="muted"> · {ruleSummary(rule)}</span>
        <div className="muted">
          {scope} · {rule.enabled ? "On" : "Off"} · methodology v{rule.methodology_version} · created{" "}
          {formatAsOf(rule.created_at)}
        </div>
      </div>
      <div className="alerts-row-actions">
        <button
          type="button"
          className="btn"
          disabled={pending}
          onClick={() => onToggle(rule)}
        >
          {rule.enabled ? "Disable" : "Enable"}
        </button>
        <button
          type="button"
          className="btn"
          disabled={pending}
          onClick={() => onDelete(rule)}
        >
          Delete
        </button>
      </div>
    </li>
  );
});

interface FiredRowProps {
  fired: AlertFired;
  familyLabel: string;
  ruleFamily: string;
  company: ReactNode;
  pending: boolean;
  onAck: (fired: AlertFired) => void;
}

const FiredRow = memo(function FiredRow({ fired, familyLabel, ruleFamily, company, pending, onAck }: FiredRowProps) {
  const acked = fired.acked_at !== null && fired.acked_at !== undefined;
  const entries = snapshotEntries(fired.inputs_snapshot ?? {});
  return (
    <li className={acked ? "alerts-fired alerts-dimmed" : "alerts-fired"}>
      <div>
        <strong>{familyLabel}</strong>
        <span className="muted"> · {company}</span>
        <div className="muted">
          Fired {formatAsOf(fired.fired_at)}
          {acked ? ` · acknowledged ${formatAsOf(fired.acked_at as string)}` : " · unacknowledged"}
        </div>
        <FiredSummary family={ruleFamily} snapshot={fired.inputs_snapshot ?? {}} />
        {entries.length > 0 ? (
          <details className="alerts-details">
            <summary className="muted">Technical details</summary>
            <ul className="alerts-snapshot" title="Inputs behind this alert: fact ids, price as-of and methodology version where recorded">
              {entries.map(([key, value]) => (
                <li key={key}>
                  <span className="alerts-snapshot-key">{key}</span>: {value}
                </li>
              ))}
            </ul>
          </details>
        ) : (
          <div className="muted">No inputs snapshot recorded.</div>
        )}
      </div>
      {acked ? (
        <span className="alerts-tag">Acknowledged</span>
      ) : (
        <div className="alerts-row-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={pending}
            onClick={() => onAck(fired)}
          >
            Acknowledge
          </button>
        </div>
      )}
    </li>
  );
});

export default function Alerts() {
  const queryClient = useQueryClient();
  const {
    data: rules,
    isLoading: rulesLoading,
    error: rulesError,
    refetch: refetchRules,
  } = useAlertRules();
  const {
    data: fired,
    isLoading: firedLoading,
    error: firedError,
    refetch: refetchFired,
  } = useFiredAlerts();
  const { data: watchlists } = useWatchlists();
  const { data: companiesPage1 } = useCompanies({ page_size: 200 });
  const { data: companiesPage2 } = useCompanies({ page_size: 200, page: 2 });

  const [family, setFamily] = useState<AlertFamily>("price");
  const [threshold, setThreshold] = useState("");
  const [direction, setDirection] = useState<"above" | "below">("above");
  const [gapPct, setGapPct] = useState("");
  const [thresholdPct, setThresholdPct] = useState("");
  const [ticker, setTicker] = useState("");
  const [watchlistId, setWatchlistId] = useState("");
  const [scope, setScope] = useState<"company" | "watchlist" | "universe">("company");
  const [enabled, setEnabled] = useState(true);
  const [showAcked, setShowAcked] = useState(true);
  const [tab, setTab] = useState<"build" | "rules" | "fired">("build");
  const [creating, setCreating] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const watchlistNames = useMemo(() => {
    const names = new Map<string, string>();
    for (const list of watchlists ?? []) names.set(list.id, list.name);
    return names;
  }, [watchlists]);

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

  const companyById = useMemo(() => {
    const byId = new Map<string, { ticker: string; name: string }>();
    for (const page of [companiesPage1, companiesPage2]) {
      for (const c of page?.items ?? []) byId.set(c.id, { ticker: c.ticker, name: c.name });
    }
    return byId;
  }, [companiesPage1, companiesPage2]);

  const companyLabel = (id: string | null): ReactNode => {
    if (!id) return null;
    const found = companyById.get(id);
    if (!found) return <span title={id}>Company {id.slice(0, 8)}…</span>;
    return (
      <span>
        Company: <Link to={`/companies/${found.ticker}`}>{found.ticker}</Link>
        <span className="muted"> — {found.name}</span>
      </span>
    );
  };

  const watchlistLink = (id: string | null): ReactNode => {
    if (!id) return null;
    const name = watchlistNames.get(id);
    if (!name) return <span title={id}>Unknown list</span>;
    return <Link to={`/watchlists?list=${encodeURIComponent(id)}`}>{name}</Link>;
  };

  const documentRules = useMemo(
    () => (rules ?? []).filter((rule) => rule.family === "document"),
    [rules],
  );
  const otherRules = useMemo(
    () => (rules ?? []).filter((rule) => rule.family !== "document"),
    [rules],
  );
  const documentByList = useMemo(() => {
    const groups = new Map<string, AlertRule[]>();
    for (const rule of documentRules) {
      const key = rule.watchlist_id ?? "unscoped";
      const group = groups.get(key) ?? [];
      group.push(rule);
      groups.set(key, group);
    }
    return [...groups.entries()];
  }, [documentRules]);

  const ruleFamilyById = useMemo(() => {
    const byId = new Map<string, string>();
    for (const rule of rules ?? []) byId.set(rule.id, rule.family);
    return byId;
  }, [rules]);

  const visibleFired = useMemo(() => {
    const rows = fired ?? [];
    return showAcked ? rows : rows.filter((row) => row.acked_at === null);
  }, [fired, showAcked]);

  const handleCreate = async (): Promise<void> => {
    setFormError(null);
    const rawFamily: string = family;
    if (!isFamily(rawFamily)) {
      setFormError("Choose one of the four alert families.");
      return;
    }
    // One scope, one meaning: the radio decides which picker below applies.
    const effectiveScope = rawFamily === "document" ? "watchlist" : scope;
    let resolvedCompanyId: string | undefined;
    let resolvedWatchlistId: string | undefined;
    if (effectiveScope === "company") {
      const rawTicker = ticker.trim().toUpperCase();
      if (rawTicker === "") {
        setFormError("Pick a company ticker — or switch scope to a list or the whole universe.");
        return;
      }
      let company = null;
      try {
        company = await getCompanyByTicker(rawTicker);
      } catch (err) {
        setFormError(err instanceof Error ? err.message : "Could not look up that ticker.");
        return;
      }
      if (!company) {
        setFormError(`No company with ticker "${rawTicker}" — pick one from the list.`);
        return;
      }
      resolvedCompanyId = company.id;
    } else if (effectiveScope === "watchlist") {
      if (watchlistId.trim() === "") {
        setFormError(
          rawFamily === "document"
            ? "Document alerts are per-list: pick the watchlist to watch."
            : "Pick a watchlist — or switch scope to a company or the whole universe.",
        );
        return;
      }
      resolvedWatchlistId = watchlistId.trim();
    }
    let params: Record<string, unknown> = {};
    if (rawFamily === "price") {
      const value = Number.parseFloat(threshold);
      if (!Number.isFinite(value)) {
        setFormError("Price alerts need a numeric threshold.");
        return;
      }
      params = { threshold: value, direction };
    } else if (rawFamily === "valuation_gap") {
      const value = Number.parseFloat(gapPct);
      if (!Number.isFinite(value) || value <= 0) {
        setFormError("Valuation-gap alerts need a gap percent above zero.");
        return;
      }
      params = { gap_pct: value };
    } else if (rawFamily === "score_change") {
      const value = Number.parseFloat(thresholdPct);
      if (!Number.isFinite(value) || value <= 0) {
        setFormError("Score-change alerts need a threshold percent above zero.");
        return;
      }
      params = { threshold_pct: value };
    }
    if (
      (rawFamily === "document" || effectiveScope === "watchlist") &&
      resolvedWatchlistId === undefined
    ) {
      setFormError("Document alerts are per-list: pick the watchlist to watch.");
      return;
    }
    setCreating(true);
    try {
      await createAlertRule({
        family: rawFamily,
        params,
        watchlist_id: resolvedWatchlistId,
        company_id: resolvedCompanyId,
        enabled,
      });
      setTicker("");
      await queryClient.invalidateQueries({ queryKey: ["alertRules"] });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not create the alert rule.");
    } finally {
      setCreating(false);
    }
  };

  const handleToggle = async (rule: AlertRule): Promise<void> => {
    setActionError(null);
    setPendingId(rule.id);
    try {
      await updateAlertRule(rule.id, { enabled: !rule.enabled });
      await queryClient.invalidateQueries({ queryKey: ["alertRules"] });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not update the rule.");
    } finally {
      setPendingId(null);
    }
  };

  const handleDelete = async (rule: AlertRule): Promise<void> => {
    if (!window.confirm(`Delete this ${rule.family} alert rule?`)) return;
    setActionError(null);
    setPendingId(rule.id);
    try {
      await deleteAlertRule(rule.id);
      await queryClient.invalidateQueries({ queryKey: ["alertRules"] });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not delete the rule.");
    } finally {
      setPendingId(null);
    }
  };

  const handleAck = async (row: AlertFired): Promise<void> => {
    setActionError(null);
    setPendingId(row.id);
    try {
      await ackFiredAlert(row.id);
      await queryClient.invalidateQueries({ queryKey: ["firedAlerts"] });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not acknowledge the alert.");
    } finally {
      setPendingId(null);
    }
  };

  if (rulesLoading || firedLoading) {
    return <div className="loading">Loading alerts...</div>;
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Alerts</h1>
          <p className="subtitle">
            In-app watchers only — no email or push. Alerts propose a check; they never advise action.
          </p>
        </div>
      </div>

      {actionError && (
        <div className="alert alert-error">
          {actionError}{" "}
          <button className="link-btn" onClick={() => setActionError(null)}>
            Dismiss
          </button>
        </div>
      )}

      <div className="alerts-tabs" role="tablist" aria-label="Alerts sections">
        {(
          [
            ["build", "Build"],
            ["rules", `Rules${rules?.length ? ` (${rules.length})` : ""}`],
            [
              "fired",
              `Fired${fired ? ` (${visibleFired.length}/${fired.length})` : ""}`,
            ],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? "alerts-tab alerts-tab-active" : "alerts-tab"}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "build" ? (
      <div className="alerts-layout">
        <section className="card" aria-label="New alert rule">
          <h2>New rule</h2>
          <div className="alerts-form">
            <label className="alerts-field">
              Family
              <select value={family} onChange={(e) => setFamily(e.target.value as AlertFamily)}>
                {FAMILIES.map((value) => (
                  <option key={value} value={value}>
                    {FAMILY_LABELS[value]}
                  </option>
                ))}
              </select>
            </label>
            <p className="muted">{FAMILY_HINTS[family]}</p>

            {family === "price" ? (
              <>
                <label className="alerts-field">
                  Threshold (price)
                  <input
                    type="number"
                    inputMode="decimal"
                    value={threshold}
                    onChange={(e) => setThreshold(e.target.value)}
                    placeholder="e.g. 42.5"
                  />
                </label>
                <label className="alerts-field">
                  Direction
                  <select value={direction} onChange={(e) => setDirection(e.target.value as "above" | "below")}>
                    <option value="above">Above (crosses up through)</option>
                    <option value="below">Below (crosses down through)</option>
                  </select>
                </label>
              </>
            ) : null}
            {family === "valuation_gap" ? (
              <label className="alerts-field">
                Gap percent
                <input
                  type="number"
                  inputMode="decimal"
                  value={gapPct}
                  onChange={(e) => setGapPct(e.target.value)}
                  placeholder="e.g. 20"
                />
              </label>
            ) : null}
            {family === "score_change" ? (
              <label className="alerts-field">
                Threshold percent
                <input
                  type="number"
                  inputMode="decimal"
                  value={thresholdPct}
                  onChange={(e) => setThresholdPct(e.target.value)}
                  placeholder="e.g. 10"
                />
              </label>
            ) : null}
            {family === "document" ? (
              <p className="muted">Document rules carry no parameters — pick the list to watch.</p>
            ) : null}

            <fieldset className="alerts-scope">
              <legend>Scope — what does this rule watch?</legend>
              {family === "document" ? (
                <p className="muted">
                  Document alerts are per-list: pick the watchlist whose filings to watch.
                </p>
              ) : (
                <>
                  <label className="alerts-check">
                    <input
                      type="radio"
                      name="alert-scope"
                      value="company"
                      checked={scope === "company"}
                      onChange={() => setScope("company")}
                    />
                    This company only
                  </label>
                  <label className="alerts-check">
                    <input
                      type="radio"
                      name="alert-scope"
                      value="watchlist"
                      checked={scope === "watchlist"}
                      onChange={() => setScope("watchlist")}
                    />
                    One watchlist
                  </label>
                  <label className="alerts-check">
                    <input
                      type="radio"
                      name="alert-scope"
                      value="universe"
                      checked={scope === "universe"}
                      onChange={() => setScope("universe")}
                    />
                    Whole universe
                  </label>
                  <p className="muted">
                    {scope === "company"
                      ? "Checks the chosen company only."
                      : scope === "watchlist"
                        ? "Checks every company on the chosen list."
                        : "Checks every tracked company. Use sparingly — it fires for the whole market."}
                  </p>
                </>
              )}
              {(family === "document" || scope === "watchlist") && (
                <label className="alerts-field">
                  Watchlist
                  <select value={watchlistId} onChange={(e) => setWatchlistId(e.target.value)}>
                    <option value="">Select a list…</option>
                    {(watchlists ?? []).map((list) => (
                      <option key={list.id} value={list.id}>
                        {list.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {family !== "document" && scope === "company" && (
                <label className="alerts-field">
                  Company ticker
                  <select
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value)}
                    disabled={companiesLoading}
                  >
                    <option value="">Select a company…</option>
                    {companyOptions.map((c) => (
                      <option key={c.ticker} value={c.ticker}>
                        {c.ticker} — {c.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </fieldset>
            <label className="alerts-check">
              <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
              Enabled
            </label>

            {formError ? <div className="alert alert-error">{formError}</div> : null}
            <button type="button" className="btn btn-primary" disabled={creating} onClick={handleCreate}>
              {creating ? "Creating…" : "Create rule"}
            </button>
          </div>
        </section>
      </div>
      ) : null}

      {tab === "rules" ? (
      <section className="card" aria-label="Alert rules">
          <h2>Rules</h2>
          {rulesError ? (
            <div className="alert alert-error">
              Couldn&apos;t load alert rules.{" "}
              <button className="link-btn" onClick={() => refetchRules()}>
                Retry
              </button>
            </div>
          ) : null}
          {!rulesError && (rules ?? []).length === 0 ? (
            <div className="empty">No alert rules yet. Build the first one on the left.</div>
          ) : null}
          {otherRules.length > 0 ? (
            <ul className="alerts-list">
              {otherRules.map((rule) => (
                <RuleRow
                  key={rule.id}
                  rule={rule}
                  scope={scopeLabel(rule, watchlistLink, companyLabel)}
                  pending={pendingId === rule.id}
                  onToggle={handleToggle}
                  onDelete={handleDelete}
                />
              ))}
            </ul>
          ) : null}
          <h3>Document alerts by list</h3>
          {documentByList.length === 0 ? (
            <p className="muted">No per-list document toggles yet.</p>
          ) : (
            documentByList.map(([listId, group]) => (
              <div key={listId}>
                <h4 className="alerts-group-title">
                  {listId === "unscoped" ? "No list scope" : watchlistLink(listId)}
                </h4>
                <ul className="alerts-list">
                  {group.map((rule) => (
                    <RuleRow
                      key={rule.id}
                      rule={rule}
                      scope={scopeLabel(rule, watchlistLink, companyLabel)}
                      pending={pendingId === rule.id}
                      onToggle={handleToggle}
                      onDelete={handleDelete}
                    />
                  ))}
                </ul>
              </div>
            ))
          )}
        </section>
      ) : null}

      {tab === "fired" ? (
      <section className="card" aria-label="Fired alerts">
        <div className="alerts-feed-header">
          <h2>Fired alerts</h2>
          <label className="alerts-check">
            <input
              type="checkbox"
              checked={showAcked}
              onChange={(e) => setShowAcked(e.target.checked)}
            />
            Show acknowledged
          </label>
        </div>
        {firedError ? (
          <div className="alert alert-error">
            Couldn&apos;t load fired alerts.{" "}
            <button className="link-btn" onClick={() => refetchFired()}>
              Retry
            </button>
          </div>
        ) : null}
        {!firedError && visibleFired.length === 0 ? (
          <div className="empty">
            {(fired ?? []).length === 0
              ? "Nothing has fired yet."
              : "No unacknowledged alerts — everything here is acknowledged."}
          </div>
        ) : null}
        <ul className="alerts-list">
          {visibleFired.map((row) => (
            <FiredRow
              key={row.id}
              fired={row}
              familyLabel={FAMILY_LABELS[(ruleFamilyById.get(row.rule_id) ?? "") as AlertFamily] ?? "Alert"}
              ruleFamily={ruleFamilyById.get(row.rule_id) ?? ""}
              company={companyLabel(row.company_id)}
              pending={pendingId === row.id}
              onAck={handleAck}
            />
          ))}
        </ul>
      </section>
      ) : null}
    </div>
  );
}
