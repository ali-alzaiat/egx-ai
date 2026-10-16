import "./Alerts.css";

import { memo, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ackFiredAlert,
  createAlertRule,
  deleteAlertRule,
  updateAlertRule,
  useAlertRules,
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

function scopeLabel(rule: AlertRule, watchlistName: (id: string | null) => string): string {
  if (rule.watchlist_id) return `List: ${watchlistName(rule.watchlist_id)}`;
  if (rule.company_id) return `Company: ${rule.company_id}`;
  return "Whole universe";
}

interface RuleRowProps {
  rule: AlertRule;
  scope: string;
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
  pending: boolean;
  onAck: (fired: AlertFired) => void;
}

const FiredRow = memo(function FiredRow({ fired, familyLabel, pending, onAck }: FiredRowProps) {
  const acked = fired.acked_at !== null && fired.acked_at !== undefined;
  const entries = snapshotEntries(fired.inputs_snapshot ?? {});
  return (
    <li className={acked ? "alerts-fired alerts-dimmed" : "alerts-fired"}>
      <div>
        <strong>{familyLabel}</strong>
        <span className="muted"> · company {fired.company_id}</span>
        <div className="muted">
          Fired {formatAsOf(fired.fired_at)}
          {acked ? ` · acknowledged ${formatAsOf(fired.acked_at as string)}` : " · unacknowledged"}
        </div>
        {entries.length > 0 ? (
          <ul className="alerts-snapshot" title="Inputs behind this alert: fact ids, price as-of and methodology version where recorded">
            {entries.map(([key, value]) => (
              <li key={key}>
                <span className="alerts-snapshot-key">{key}</span>: {value}
              </li>
            ))}
          </ul>
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

  const [family, setFamily] = useState<AlertFamily>("price");
  const [threshold, setThreshold] = useState("");
  const [direction, setDirection] = useState<"above" | "below">("above");
  const [gapPct, setGapPct] = useState("");
  const [thresholdPct, setThresholdPct] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [watchlistId, setWatchlistId] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [showAcked, setShowAcked] = useState(true);
  const [creating, setCreating] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const watchlistNames = useMemo(() => {
    const names = new Map<string, string>();
    for (const list of watchlists ?? []) names.set(list.id, list.name);
    return names;
  }, [watchlists]);

  const watchlistName = (id: string | null): string => {
    if (!id) return "—";
    return watchlistNames.get(id) ?? id;
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
    if (rawFamily === "document" && watchlistId.trim() === "") {
      setFormError("Document alerts are per-list: pick a watchlist.");
      return;
    }
    setCreating(true);
    try {
      await createAlertRule({
        family: rawFamily,
        params,
        watchlist_id: watchlistId.trim() === "" ? undefined : watchlistId.trim(),
        company_id: companyId.trim() === "" ? undefined : companyId.trim(),
        enabled,
      });
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

            <label className="alerts-field">
              Watchlist scope (optional{family === "document" ? ", required here" : ""})
              <select value={watchlistId} onChange={(e) => setWatchlistId(e.target.value)}>
                <option value="">No list scope</option>
                {(watchlists ?? []).map((list) => (
                  <option key={list.id} value={list.id}>
                    {list.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="alerts-field">
              Company ID scope (optional)
              <input
                type="text"
                value={companyId}
                onChange={(e) => setCompanyId(e.target.value)}
                placeholder="Company UUID"
              />
            </label>
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
                  scope={scopeLabel(rule, watchlistName)}
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
                  {listId === "unscoped" ? "No list scope" : watchlistName(listId)}
                </h4>
                <ul className="alerts-list">
                  {group.map((rule) => (
                    <RuleRow
                      key={rule.id}
                      rule={rule}
                      scope={scopeLabel(rule, watchlistName)}
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
      </div>

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
              pending={pendingId === row.id}
              onAck={handleAck}
            />
          ))}
        </ul>
      </section>
    </div>
  );
}
