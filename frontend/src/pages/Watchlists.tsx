import "./shared/fields.css";
import "./Watchlists.css";

import { useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  addWatchlistEntry,
  createWatchlist,
  deleteWatchlistEntry,
  updateWatchlistEntry,
  useWatchlistEntries,
  useWatchlists,
} from "../api/client";
import { ShariahBadge, Tag } from "../components/ui/Badges";
import { CompanyName } from "../components/ui/CompanyName";
import CompanySearch from "../components/ui/CompanySearch";
import DataTable, { StockCell, type Column } from "../components/ui/DataTable";
import { Missing } from "../components/ui/Missing";
import { PageHeader } from "../components/ui/PageHeader";
import { PageTitle } from "../components/ui/PageTitle";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtNum, fmtPrice, plural } from "../lib/format";
import { useMediaQuery } from "../lib/useMediaQuery";
import type { Company, WatchlistEntry } from "../types";
import { describeError, type ErrorView } from "./shared/apiError";
import { Field, FieldGroup } from "./shared/Field";
import { ErrorMessage, FormMessage } from "./shared/FormMessage";
import { badgeAvailable, shariahVerdictOf, staleAge } from "./tracking/watchlistBadges";

/** Edit panel for one entry: group and note (thesis links follow the latest thesis automatically). */
function EditEntry({
  entry,
  watchlistId,
  onSaved,
  onCancel,
}: {
  entry: WatchlistEntry;
  watchlistId: string;
  onSaved: () => Promise<void>;
  onCancel: () => void;
}) {
  const { t } = useLang();
  const [group, setGroup] = useState(entry.group ?? "");
  const [note, setNote] = useState(entry.note ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ErrorView | null>(null);

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await updateWatchlistEntry(watchlistId, entry.id, {
        ...(group.trim() !== (entry.group ?? "") ? { group: group.trim() } : {}),
        ...(note.trim() !== (entry.note ?? "") ? { note: note.trim() } : {}),
      });
      await onSaved();
    } catch (err) {
      setError(describeError(err, t, "err_generic"));
      setSaving(false);
    }
  };

  return (
    <form className="card panel" onSubmit={(e) => void submit(e)}>
      <h3>{t("wl_edit_title", { ticker: entry.company_ticker ?? t("trk_unknown_company") })}</h3>
      <div className="fld-row">
        <Field label={t("wl_group")}>
          <input value={group} maxLength={100} onChange={(e) => setGroup(e.target.value)} placeholder={t("wl_group_placeholder")} />
        </Field>
        <Field label={t("wl_note")}>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("wl_note_placeholder")} />
        </Field>
      </div>
      {error && <ErrorMessage view={error} />}
      <div className="fld-actions">
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? t("wl_saving") : t("wl_save")}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={saving}>
          {t("wl_cancel")}
        </button>
      </div>
    </form>
  );
}

/** Add-a-company form: a company picker plus an optional note; no ids typed. */
function AddCompany({ watchlistId, onAdded }: { watchlistId: string; onAdded: () => Promise<void> }) {
  const { t } = useLang();
  const [company, setCompany] = useState<Company | null>(null);
  const [note, setNote] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<ErrorView | null>(null);
  const [added, setAdded] = useState<string | null>(null);

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!company) return;
    setAdding(true);
    setError(null);
    setAdded(null);
    try {
      await addWatchlistEntry(watchlistId, {
        company_id: company.id,
        ...(note.trim() !== "" ? { note: note.trim() } : {}),
      });
      setAdded(company.ticker);
      setCompany(null);
      setNote("");
      await onAdded();
    } catch (err) {
      setError(describeError(err, t, "err_generic"));
    } finally {
      setAdding(false);
    }
  };

  return (
    <form className="card panel" onSubmit={(e) => void submit(e)}>
      <h3>{t("wl_add_title")}</h3>
      <div className="fld-row">
        <FieldGroup label={t("wl_company")}>
          <CompanySearch
            mode="picker"
            value={company}
            onSelect={(c) => {
              setCompany(c);
              setAdded(null);
            }}
            onClear={() => setCompany(null)}
          />
        </FieldGroup>
        <Field label={t("wl_note_optional")}>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("wl_note_placeholder")} />
        </Field>
        <div>
          <button type="submit" className="btn btn-primary" disabled={adding || !company}>
            {adding ? t("wl_adding") : t("wl_add")}
          </button>
        </div>
      </div>
      {error && <ErrorMessage view={error} />}
      {added && <FormMessage kind="success" text={t("wl_added", { ticker: added })} />}
    </form>
  );
}

/** Inline "new list" form: name plus Create. */
function NewList({ onCreated }: { onCreated: (id: string) => void }) {
  const { t } = useLang();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<ErrorView | null>(null);

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    const trimmed = name.trim();
    if (trimmed === "") return;
    setCreating(true);
    setError(null);
    try {
      const created = await createWatchlist(trimmed);
      await queryClient.invalidateQueries({ queryKey: ["watchlists"] });
      setName("");
      onCreated(created.id);
    } catch (err) {
      setError(describeError(err, t, "err_generic"));
    } finally {
      setCreating(false);
    }
  };

  return (
    <form className="wl-new" onSubmit={(e) => void submit(e)}>
      <Field label={t("wl_new_list")}>
        <input value={name} maxLength={100} onChange={(e) => setName(e.target.value)} placeholder={t("wl_new_list_placeholder")} />
      </Field>
      <button type="submit" className="btn btn-secondary" disabled={creating || name.trim() === ""}>
        {creating ? t("wl_creating") : t("wl_create")}
      </button>
      {error && <ErrorMessage view={error} />}
    </form>
  );
}

export default function Watchlists() {
  const { t, locale } = useLang();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const narrow = useMediaQuery("(max-width: 1023px)");
  const lists = useWatchlists();
  const items = lists.data ?? [];
  const requested = params.get("list");
  const selected = items.find((l) => l.id === requested) ?? items[0] ?? null;
  const selectedId = selected?.id;
  const entries = useWatchlistEntries(selectedId);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<ErrorView | null>(null);

  const select = (id: string): void => {
    setEditingId(null);
    setConfirmId(null);
    setRemoveError(null);
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("list", id);
        return next;
      },
      { replace: true },
    );
  };

  const refreshEntries = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ["watchlistEntries", selectedId] });
  };

  const remove = async (entry: WatchlistEntry): Promise<void> => {
    if (!selectedId) return;
    setBusyId(entry.id);
    setRemoveError(null);
    try {
      await deleteWatchlistEntry(selectedId, entry.id);
      setConfirmId(null);
      await refreshEntries();
    } catch (err) {
      setRemoveError(describeError(err, t, "err_generic"));
    } finally {
      setBusyId(null);
    }
  };

  const columns = useMemo<Column<WatchlistEntry>[]>(
    () => [
      {
        id: "stock",
        header: t("wl_col_stock"),
        sticky: true,
        sortable: true,
        sortValue: (e) => e.company_ticker,
        cell: (e) =>
          e.company_ticker ? (
            <StockCell
              ticker={e.company_ticker}
              href={`/companies/${encodeURIComponent(e.company_ticker)}`}
              name={e.company_name ? <CompanyName name={e.company_name} /> : null}
            />
          ) : (
            <Missing localized={t("trk_unknown_company")} />
          ),
      },
      {
        id: "note",
        header: t("wl_col_note"),
        cell: (e) => (
          <span className="wl-note">
            {e.note ? <span title={e.note}>{e.note}</span> : <Missing localized={t("wl_no_note")} />}
            {e.group ? <Tag title={t("wl_group_title")}>{e.group}</Tag> : null}
          </span>
        ),
      },
      {
        id: "price",
        header: t("wl_col_price"),
        type: "num",
        sortable: true,
        sortValue: (e) => (badgeAvailable(e.price) ? Number(e.price.value) : null),
        cell: (e) => {
          if (!badgeAvailable(e.price)) return <Missing reason={e.price?.reason} />;
          const age = staleAge(e.staleness);
          const asOf = badgeAvailable(e.as_of) ? fmtDate(locale, e.as_of.value) : null;
          return (
            <span className="wl-price" title={badgeAvailable(e.change) ? e.change.value : undefined}>
              <span>{fmtPrice(locale, e.price.value) ?? <Missing />}</span>
              <span className="text-note">{asOf ? t("wl_as_of", { date: asOf }) : <Missing reason={e.as_of?.reason} />}</span>
              {age !== null ? (
                <Tag title={e.staleness?.reason ?? undefined}>
                  {plural(locale, age, {
                    one: t("wl_stale_one"),
                    two: t("wl_stale_two"),
                    few: t("wl_stale_few"),
                    other: t("wl_stale_other"),
                  })}
                </Tag>
              ) : null}
            </span>
          );
        },
      },
      {
        id: "score",
        header: t("wl_col_score"),
        type: "num",
        sortable: true,
        sortValue: (e) => (badgeAvailable(e.score) ? Number(e.score.value) : null),
        cell: (e) =>
          badgeAvailable(e.score) ? (
            fmtNum(locale, e.score.value, { maximumFractionDigits: 1 })
          ) : (
            <Missing reason={e.score?.reason} />
          ),
      },
      {
        id: "shariah",
        header: t("wl_col_shariah"),
        cell: (e) => {
          const verdict = shariahVerdictOf(e.shariah_state);
          return verdict ? <ShariahBadge verdict={verdict} /> : <Missing reason={e.shariah_state?.reason} />;
        },
      },
      {
        id: "thesis",
        header: t("wl_col_thesis"),
        cell: (e) =>
          badgeAvailable(e.thesis_link_badge) && e.company_ticker ? (
            <Link to={`/companies/${encodeURIComponent(e.company_ticker)}/thesis`}>{t("wl_open_thesis")}</Link>
          ) : (
            <Missing reason={e.thesis_link_badge?.reason} />
          ),
      },
      {
        id: "actions",
        header: t("wl_col_actions"),
        cell: (e) =>
          confirmId === e.id ? (
            <span className="wl-actions">
              <button type="button" className="link-btn" disabled={busyId === e.id} onClick={() => void remove(e)}>
                {busyId === e.id ? t("wl_removing") : t("wl_confirm_remove")}
              </button>
              <button type="button" className="link-btn" onClick={() => setConfirmId(null)}>
                {t("wl_cancel")}
              </button>
            </span>
          ) : (
            <span className="wl-actions">
              <button
                type="button"
                className="link-btn"
                onClick={() => {
                  setEditingId(e.id);
                  setConfirmId(null);
                }}
              >
                {t("wl_edit")}
              </button>
              <button
                type="button"
                className="link-btn"
                onClick={() => {
                  setConfirmId(e.id);
                  setEditingId(null);
                }}
              >
                {t("wl_remove")}
              </button>
            </span>
          ),
      },
    ],
    // `remove` closes over selectedId and refreshEntries; both are derived from the same inputs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, locale, confirmId, busyId, selectedId],
  );

  const rows = entries.data ?? [];
  const editing = rows.find((r) => r.id === editingId) ?? null;

  const listPicker = narrow ? (
    <Field label={t("wl_lists")}>
      <select value={selectedId ?? ""} onChange={(e) => select(e.target.value)}>
        {items.map((l) => (
          <option key={l.id} value={l.id}>
            {l.name}
          </option>
        ))}
      </select>
    </Field>
  ) : (
    <nav className="wl-lists" aria-label={t("wl_lists")}>
      <h2 className="section-title">{t("wl_lists")}</h2>
      <ul>
        {items.map((l) => (
          <li key={l.id}>
            <button
              type="button"
              className="wl-list-item"
              aria-current={l.id === selectedId ? "true" : undefined}
              onClick={() => select(l.id)}
            >
              {l.name}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );

  return (
    <div className="page">
      <PageTitle parts={[t("nav_watchlists")]} />
      <PageHeader title={t("nav_watchlists")} subtitle={t("wl_subtitle")} />

      {lists.isLoading ? (
        <LoadingState thing={t("wl_things_lists")} />
      ) : lists.isError ? (
        <ErrorState thing={t("wl_things_lists")} onRetry={() => void lists.refetch()} />
      ) : (
        <div className="wl-layout">
          <aside className="wl-side">
            {items.length > 0 && listPicker}
            <NewList onCreated={select} />
          </aside>

          <section className="wl-main" aria-label={selected?.name ?? t("nav_watchlists")}>
            {selected === null ? (
              <EmptyState>{t("wl_empty_lists")}</EmptyState>
            ) : (
              <>
                <h2 className="section-title">{selected.name}</h2>
                <AddCompany watchlistId={selected.id} onAdded={refreshEntries} />
                {editing && (
                  <EditEntry
                    key={editing.id}
                    entry={editing}
                    watchlistId={selected.id}
                    onSaved={async () => {
                      setEditingId(null);
                      await refreshEntries();
                    }}
                    onCancel={() => setEditingId(null)}
                  />
                )}
                {removeError && <ErrorMessage view={removeError} />}
                {entries.isError ? (
                  <ErrorState thing={t("wl_things_entries")} onRetry={() => void entries.refetch()} />
                ) : (
                  <DataTable
                    columns={columns}
                    rows={rows}
                    rowKey={(e) => e.id}
                    caption={selected.name}
                    loading={entries.isLoading}
                    loadingThing={t("wl_things_entries")}
                    meta={plural(locale, rows.length, {
                      zero: t("wl_count_zero"),
                      one: t("wl_count_one"),
                      two: t("wl_count_two"),
                      few: t("wl_count_few"),
                      many: t("wl_count_many"),
                      other: t("wl_count_other"),
                    })}
                    footnote={t("wl_footnote")}
                    empty={<EmptyState>{t("wl_empty_list")}</EmptyState>}
                    cardFields={["price", "score", "shariah", "actions"]}
                    hideDensityToggle
                  />
                )}
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
