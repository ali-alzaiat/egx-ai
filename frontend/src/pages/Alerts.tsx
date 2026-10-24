import "./shared/fields.css";
import "./Alerts.css";

import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
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
import { Tag } from "../components/ui/Badges";
import CompanySearch from "../components/ui/CompanySearch";
import { Notice } from "../components/ui/Notice";
import { PageHeader } from "../components/ui/PageHeader";
import { PageTitle } from "../components/ui/PageTitle";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtInt } from "../lib/format";
import type { AlertFired, AlertRule, Company, Watchlist } from "../types";
import { describeError, type ErrorView } from "./shared/apiError";
import { Field, FieldGroup } from "./shared/Field";
import { ErrorMessage, FormMessage } from "./shared/FormMessage";
import {
  FAMILIES,
  FAMILY_HINT,
  FAMILY_LABEL,
  buildParams,
  familyLabel,
  firedSummary,
  resolveScope,
  ruleSummary,
  snapshotEntries,
  type AlertFamily,
  type Scope,
} from "./tracking/alertsFormat";
import { CompanyRef } from "./tracking/CompanyRef";
import { fmtDateTime } from "./tracking/dateTime";
import { useCompanyIndex } from "./shared/useCompanyIndex";

type TabKey = "build" | "rules" | "fired";
const TABS: readonly TabKey[] = ["build", "rules", "fired"];

function isTab(value: string | null): value is TabKey {
  return value !== null && (TABS as readonly string[]).includes(value);
}

/** The "New rule" form. Scope decides which picker applies; document rules are per-list. */
function BuildRule({ watchlists, onCreated }: { watchlists: readonly Watchlist[]; onCreated: () => Promise<void> }) {
  const { t } = useLang();
  const [family, setFamily] = useState<AlertFamily>("price");
  const [threshold, setThreshold] = useState("");
  const [direction, setDirection] = useState<"above" | "below">("above");
  const [gapPct, setGapPct] = useState("");
  const [thresholdPct, setThresholdPct] = useState("");
  const [scope, setScope] = useState<Scope>("company");
  const [company, setCompany] = useState<Company | null>(null);
  const [watchlistId, setWatchlistId] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [creating, setCreating] = useState(false);
  const [invalid, setInvalid] = useState<string | null>(null);
  const [failure, setFailure] = useState<ErrorView | null>(null);
  const [created, setCreated] = useState(false);

  const showList = family === "document" || scope === "watchlist";
  const showCompany = family !== "document" && scope === "company";

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    setInvalid(null);
    setFailure(null);
    setCreated(false);
    const scoped = resolveScope(family, scope, company, watchlistId);
    if (!scoped.ok) {
      setInvalid(t(scoped.error));
      return;
    }
    const built = buildParams(family, { threshold, direction, gapPct, thresholdPct });
    if (!built.ok) {
      setInvalid(t(built.error));
      return;
    }
    setCreating(true);
    try {
      await createAlertRule({
        family,
        params: built.params,
        watchlist_id: scoped.watchlistId,
        company_id: scoped.companyId,
        enabled,
      });
      setCompany(null);
      setCreated(true);
      await onCreated();
    } catch (err) {
      setFailure(describeError(err, t, "al_err_create"));
    } finally {
      setCreating(false);
    }
  };

  return (
    <form className="card panel al-form" onSubmit={(e) => void submit(e)}>
      <h2 className="section-title">{t("al_new_rule")}</h2>
      <Field label={t("al_family")} hint={t(FAMILY_HINT[family])}>
        <select value={family} onChange={(e) => setFamily(e.target.value as AlertFamily)}>
          {FAMILIES.map((value) => (
            <option key={value} value={value}>
              {t(FAMILY_LABEL[value])}
            </option>
          ))}
        </select>
      </Field>

      {family === "price" && (
        <>
          <Field label={t("al_threshold_price")}>
            <input
              type="number"
              dir="ltr"
              inputMode="decimal"
              step="any"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              placeholder="42.5"
            />
          </Field>
          <Field label={t("al_direction")}>
            <select value={direction} onChange={(e) => setDirection(e.target.value as "above" | "below")}>
              <option value="above">{t("al_direction_above")}</option>
              <option value="below">{t("al_direction_below")}</option>
            </select>
          </Field>
        </>
      )}
      {family === "valuation_gap" && (
        <Field label={t("al_gap_pct")}>
          <input
            type="number"
            dir="ltr"
            inputMode="decimal"
            step="any"
            value={gapPct}
            onChange={(e) => setGapPct(e.target.value)}
            placeholder="20"
          />
        </Field>
      )}
      {family === "score_change" && (
        <Field label={t("al_threshold_pct")}>
          <input
            type="number"
            dir="ltr"
            inputMode="decimal"
            step="any"
            value={thresholdPct}
            onChange={(e) => setThresholdPct(e.target.value)}
            placeholder="10"
          />
        </Field>
      )}

      <fieldset className="fld-fieldset">
        <legend>{t("al_scope")}</legend>
        {family === "document" ? (
          <p className="muted">{t("al_scope_document")}</p>
        ) : (
          <>
            {(["company", "watchlist", "universe"] as const).map((value) => (
              <label key={value} className="fld-check">
                <input
                  type="radio"
                  name="alert-scope"
                  value={value}
                  checked={scope === value}
                  onChange={() => setScope(value)}
                />
                {t(value === "company" ? "al_scope_company" : value === "watchlist" ? "al_scope_list" : "al_scope_universe")}
              </label>
            ))}
            <p className="muted">
              {t(
                scope === "company"
                  ? "al_scope_company_hint"
                  : scope === "watchlist"
                    ? "al_scope_list_hint"
                    : "al_scope_universe_hint",
              )}
            </p>
          </>
        )}
        {showList && (
          <Field label={t("al_watchlist")}>
            <select value={watchlistId} onChange={(e) => setWatchlistId(e.target.value)}>
              <option value="">{t("al_pick_list")}</option>
              {watchlists.map((list) => (
                <option key={list.id} value={list.id}>
                  {list.name}
                </option>
              ))}
            </select>
          </Field>
        )}
        {showCompany && (
          <FieldGroup label={t("al_company")}>
            <CompanySearch mode="picker" value={company} onSelect={setCompany} onClear={() => setCompany(null)} />
          </FieldGroup>
        )}
      </fieldset>

      <label className="fld-check">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        {t("al_enabled")}
      </label>

      {invalid && <FormMessage kind="error" text={invalid} />}
      {failure && <ErrorMessage view={failure} />}
      {created && <FormMessage kind="success" text={t("al_created")} />}
      <div>
        <button type="submit" className="btn btn-primary" disabled={creating}>
          {creating ? t("al_creating") : t("al_create")}
        </button>
      </div>
    </form>
  );
}

interface RuleListProps {
  rules: readonly AlertRule[];
  scopeOf: (rule: AlertRule) => ReactNode;
  pendingId: string | null;
  confirmId: string | null;
  onToggle: (rule: AlertRule) => void;
  onAskDelete: (rule: AlertRule | null) => void;
  onDelete: (rule: AlertRule) => void;
}

function RuleList({ rules, scopeOf, pendingId, confirmId, onToggle, onAskDelete, onDelete }: RuleListProps) {
  const { t, locale } = useLang();
  return (
    <ul className="al-list">
      {rules.map((rule) => (
        <li key={rule.id} className="card al-row">
          <div className="al-row-main">
            <div>
              <strong>{familyLabel(rule.family, t)}</strong> <span className="muted">{ruleSummary(rule, t, locale)}</span>
            </div>
            <div className="al-meta text-note">
              {scopeOf(rule)}
              <Tag>{rule.enabled ? t("al_on") : t("al_off")}</Tag>
              <span>
                {t("al_methodology")} <bdi dir="ltr">v{rule.methodology_version}</bdi>
              </span>
              <span>{t("al_created_on", { date: fmtDate(locale, rule.created_at) ?? t("no_value") })}</span>
            </div>
          </div>
          <div className="al-actions">
            <button type="button" className="btn btn-secondary" disabled={pendingId === rule.id} onClick={() => onToggle(rule)}>
              {rule.enabled ? t("al_disable") : t("al_enable")}
            </button>
            {confirmId === rule.id ? (
              <>
                <button type="button" className="btn btn-primary" disabled={pendingId === rule.id} onClick={() => onDelete(rule)}>
                  {t("al_confirm_delete")}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => onAskDelete(null)}>
                  {t("al_cancel")}
                </button>
              </>
            ) : (
              <button type="button" className="btn btn-secondary" disabled={pendingId === rule.id} onClick={() => onAskDelete(rule)}>
                {t("al_delete")}
              </button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function Alerts() {
  const { t, locale } = useLang();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const requested = params.get("tab");
  const tab: TabKey = isTab(requested) ? requested : "build";

  const rules = useAlertRules();
  const fired = useFiredAlerts();
  const watchlists = useWatchlists();
  const { byId: companies, loading: companiesLoading } = useCompanyIndex();

  const [showAcked, setShowAcked] = useState(true);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<ErrorView | null>(null);

  const listNames = useMemo(() => new Map((watchlists.data ?? []).map((l) => [l.id, l.name])), [watchlists.data]);
  const ruleFamilyById = useMemo(() => new Map((rules.data ?? []).map((r) => [r.id, r.family])), [rules.data]);

  const refreshRules = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ["alertRules"] });
  };

  const scopeOf = (rule: AlertRule): ReactNode => {
    if (rule.watchlist_id) {
      const name = listNames.get(rule.watchlist_id);
      return name ? (
        <span>
          {t("al_scope_prefix_list")} <Link to={`/watchlists?list=${encodeURIComponent(rule.watchlist_id)}`}>{name}</Link>
        </span>
      ) : (
        <span>{t("al_unknown_list")}</span>
      );
    }
    if (rule.company_id) return <CompanyRef company={companies.get(rule.company_id)} loading={companiesLoading} />;
    return <span>{t("al_scope_universe_short")}</span>;
  };

  const run = async (id: string, action: () => Promise<unknown>, after: () => Promise<void>): Promise<void> => {
    setActionError(null);
    setPendingId(id);
    try {
      await action();
      await after();
    } catch (err) {
      setActionError(describeError(err, t, "err_generic"));
    } finally {
      setPendingId(null);
    }
  };

  const toggle = (rule: AlertRule): Promise<void> =>
    run(rule.id, () => updateAlertRule(rule.id, { enabled: !rule.enabled }), refreshRules);
  const remove = (rule: AlertRule): Promise<void> =>
    run(
      rule.id,
      () => deleteAlertRule(rule.id),
      async () => {
        setConfirmId(null);
        await refreshRules();
      },
    );
  const acknowledge = (row: AlertFired): Promise<void> =>
    run(row.id, () => ackFiredAlert(row.id), () => queryClient.invalidateQueries({ queryKey: ["firedAlerts"] }));

  const ruleRows = useMemo(() => rules.data ?? [], [rules.data]);
  const otherRules = ruleRows.filter((r) => r.family !== "document");
  const documentGroups = useMemo(() => {
    const groups = new Map<string, AlertRule[]>();
    for (const rule of ruleRows) {
      if (rule.family !== "document") continue;
      const key = rule.watchlist_id ?? "";
      groups.set(key, [...(groups.get(key) ?? []), rule]);
    }
    return [...groups.entries()];
  }, [ruleRows]);

  const firedRows = fired.data ?? [];
  const visibleFired = showAcked ? firedRows : firedRows.filter((row) => row.acked_at === null);

  const tabLabel = (key: TabKey): string => {
    if (key === "build") return t("al_tab_build");
    if (key === "rules") {
      return ruleRows.length > 0 ? t("al_tab_rules_count", { n: fmtInt(locale, ruleRows.length) ?? "" }) : t("al_tab_rules");
    }
    return firedRows.length > 0 ? t("al_tab_fired_count", { n: fmtInt(locale, firedRows.length) ?? "" }) : t("al_tab_fired");
  };

  return (
    <div className="page">
      <PageTitle parts={[t("nav_alerts")]} />
      <PageHeader title={t("nav_alerts")} subtitle={t("al_subtitle")} />
      <Notice variant="warning">{t("al_not_evaluated")}</Notice>

      <nav className="tab-strip" aria-label={t("al_sections_aria")}>
        {TABS.map((key) => (
          <Link key={key} to={`?tab=${key}`} replace className="tab-link" aria-current={key === tab ? "page" : undefined}>
            {tabLabel(key)}
          </Link>
        ))}
      </nav>

      {actionError && <ErrorMessage view={actionError} />}

      {tab === "build" && (
        <BuildRule
          watchlists={watchlists.data ?? []}
          onCreated={async () => {
            await refreshRules();
          }}
        />
      )}

      {tab === "rules" &&
        (rules.isLoading ? (
          <LoadingState thing={t("al_things_rules")} />
        ) : rules.isError ? (
          <ErrorState thing={t("al_things_rules")} onRetry={() => void rules.refetch()} />
        ) : ruleRows.length === 0 ? (
          <EmptyState>{t("al_empty_rules")}</EmptyState>
        ) : (
          <section className="al-section" aria-label={t("al_tab_rules")}>
            {otherRules.length > 0 && (
              <RuleList
                rules={otherRules}
                scopeOf={scopeOf}
                pendingId={pendingId}
                confirmId={confirmId}
                onToggle={(r) => void toggle(r)}
                onAskDelete={(r) => setConfirmId(r?.id ?? null)}
                onDelete={(r) => void remove(r)}
              />
            )}
            <h2 className="section-title">{t("al_document_by_list")}</h2>
            {documentGroups.length === 0 ? (
              <EmptyState>{t("al_empty_document")}</EmptyState>
            ) : (
              documentGroups.map(([listId, group]) => (
                <div key={listId || "none"} className="al-group">
                  <h3 className="section-title">
                    {listId ? (
                      listNames.has(listId) ? (
                        <Link to={`/watchlists?list=${encodeURIComponent(listId)}`}>{listNames.get(listId)}</Link>
                      ) : (
                        t("al_unknown_list")
                      )
                    ) : (
                      t("al_no_list_scope")
                    )}
                  </h3>
                  <RuleList
                    rules={group}
                    scopeOf={scopeOf}
                    pendingId={pendingId}
                    confirmId={confirmId}
                    onToggle={(r) => void toggle(r)}
                    onAskDelete={(r) => setConfirmId(r?.id ?? null)}
                    onDelete={(r) => void remove(r)}
                  />
                </div>
              ))
            )}
          </section>
        ))}

      {tab === "fired" &&
        (fired.isLoading ? (
          <LoadingState thing={t("al_things_fired")} />
        ) : fired.isError ? (
          <ErrorState thing={t("al_things_fired")} onRetry={() => void fired.refetch()} />
        ) : (
          <section className="al-section" aria-label={t("al_tab_fired")}>
            <label className="fld-check">
              <input type="checkbox" checked={showAcked} onChange={(e) => setShowAcked(e.target.checked)} />
              {t("al_show_acked")}
            </label>
            {visibleFired.length === 0 ? (
              <EmptyState>{firedRows.length === 0 ? t("al_empty_fired") : t("al_empty_fired_unacked")}</EmptyState>
            ) : (
              <ul className="al-list">
                {visibleFired.map((row) => {
                  const family = ruleFamilyById.get(row.rule_id) ?? "";
                  const acked = row.acked_at !== null && row.acked_at !== undefined;
                  const snapshot = row.inputs_snapshot ?? {};
                  const entries = snapshotEntries(snapshot);
                  return (
                    <li key={row.id} className="card al-row al-fired" data-acked={acked}>
                      <div className="al-row-main">
                        <div>
                          <strong>{familyLabel(family, t)}</strong> <CompanyRef company={companies.get(row.company_id)} loading={companiesLoading} />
                        </div>
                        <p>{firedSummary(family, snapshot, t, locale)}</p>
                        <div className="al-meta text-note">
                          <span>{t("al_fired_on", { when: fmtDateTime(locale, row.fired_at) ?? t("no_value") })}</span>
                          {acked ? (
                            <Tag>{t("al_acknowledged")}</Tag>
                          ) : (
                            <span>{t("al_unacknowledged")}</span>
                          )}
                        </div>
                        {entries.length > 0 && (
                          <details className="fold">
                            <summary>{t("al_technical_details")}</summary>
                            <ul className="al-snapshot" dir="ltr">
                              {entries.map(([key, value]) => (
                                <li key={key}>
                                  <span>{key}</span>: {value}
                                </li>
                              ))}
                            </ul>
                          </details>
                        )}
                      </div>
                      {!acked && (
                        <div className="al-actions">
                          <button
                            type="button"
                            className="btn btn-primary"
                            disabled={pendingId === row.id}
                            onClick={() => void acknowledge(row)}
                          >
                            {t("al_acknowledge")}
                          </button>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        ))}
    </div>
  );
}
