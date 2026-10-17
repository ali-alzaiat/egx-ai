import './Watchlists.css'

import { memo, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  addWatchlistEntry,
  createWatchlist,
  deleteWatchlistEntry,
  getCompanyByTicker,
  updateWatchlistEntry,
  useCompanies,
  useWatchlistEntries,
  useWatchlists,
} from '../api/client'
import type { PhaseBadge, WatchlistEntry } from '../types'
import { formatAsOf, formatPrice } from '../lib/format'

function isAvailable(badge: PhaseBadge | null): boolean {
  return (
    badge !== null &&
    badge.status === 'AVAILABLE' &&
    badge.value !== null &&
    badge.value !== undefined &&
    badge.value !== ''
  )
}

function badgeTitle(badge: PhaseBadge | null): string {
  if (!badge) return 'INSUFFICIENT_DATA — the backend had no stored input for this badge'
  return badge.reason ?? badge.status
}

// Module-level (rerender-no-inline-components): never defined inside a render.
function EntryBadge({ badge }: { badge: PhaseBadge | null }) {
  return isAvailable(badge) ? (
    <span className="wl-badge" title={badgeTitle(badge)}>
      {badge?.value}
    </span>
  ) : (
    <span className="wl-badge wl-badge-missing" title={badgeTitle(badge)}>
      INSUFFICIENT_DATA
    </span>
  )
}

// Badge with a one-line next step when the input is missing (W3).
function NextStepBadge({ badge, hint }: { badge: PhaseBadge | null; hint: string }) {
  if (isAvailable(badge)) return <EntryBadge badge={badge} />;
  return (
    <>
      <EntryBadge badge={badge} />
      <div className="muted">{hint}</div>
    </>
  );
}

const STALE_AFTER_DAYS = 7;

function staleDays(staleness: PhaseBadge | null): number | null {
  if (!staleness || staleness.value === null || staleness.value === undefined) return null;
  const n = Number.parseInt(String(staleness.value), 10);
  return Number.isFinite(n) ? n : null;
}

// One price column: value + as-of sub-line; change and staleness fold into
// the tooltip, with an amber chip only when the quote is stale (W3).
function PriceCell({ entry }: { entry: WatchlistEntry }) {
  if (!isAvailable(entry.price)) return <EntryBadge badge={entry.price} />;
  const days = staleDays(entry.staleness);
  const stale = days !== null && days > STALE_AFTER_DAYS;
  const title = [
    entry.change && isAvailable(entry.change) ? `Change ${entry.change.value}` : null,
    entry.staleness?.reason ?? null,
  ]
    .filter((bit): bit is string => bit !== null && bit !== '')
    .join(' · ');
  return (
    <span title={title || undefined}>
      {formatPrice(entry.price?.value)}
      <div className="muted">as of {formatAsOf(entry.as_of?.value)}</div>
      {stale ? <div className="wl-chip wl-chip-stale">{days}d old</div> : null}
    </span>
  );
}

interface EntryRowProps {
  entry: WatchlistEntry
  watchlistId: string
  onChanged: (watchlistId: string) => Promise<void>
}

// Memoized per row (rerender-memo): editing one row never re-renders the rest.
const EntryRow = memo(function EntryRow({ entry, watchlistId, onChanged }: EntryRowProps) {
  const [editing, setEditing] = useState(false)
  const [group, setGroup] = useState(entry.group ?? '')
  const [note, setNote] = useState(entry.note ?? '')
  const [thesisLink, setThesisLink] = useState(entry.thesis_link ?? '')
  const [saving, setSaving] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async (): Promise<void> => {
    setSaving(true)
    setError(null)
    try {
      await updateWatchlistEntry(watchlistId, entry.id, {
        group: group.trim() === '' ? undefined : group.trim(),
        note: note.trim() === '' ? undefined : note.trim(),
        thesis_link: thesisLink.trim() === '' ? undefined : thesisLink.trim(),
      })
      await onChanged(watchlistId)
      setEditing(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed')
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = (): void => {
    setGroup(entry.group ?? '')
    setNote(entry.note ?? '')
    setThesisLink(entry.thesis_link ?? '')
    setError(null)
    setEditing(false)
  }

  const handleDelete = async (): Promise<void> => {
    if (!window.confirm(`Remove ${entry.company_ticker ?? entry.company_id.slice(0, 8) + '…'} from this list?`)) return
    setBusy(true)
    setError(null)
    try {
      await deleteWatchlistEntry(watchlistId, entry.id)
      await onChanged(watchlistId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed')
      setBusy(false)
    }
  }

  return (
    <tr>
      <td>
        {entry.company_ticker ? (
          <strong>
            <Link to={`/companies/${entry.company_ticker}`}>{entry.company_ticker}</Link>
          </strong>
        ) : (
          <strong title={entry.company_id}>{entry.company_id.slice(0, 8)}…</strong>
        )}
        {entry.company_name ? <div className="muted">{entry.company_name}</div> : null}
        {editing ? (
          <input
            aria-label="Group"
            value={group}
            onChange={(e) => setGroup(e.target.value)}
            placeholder="e.g. banks"
          />
        ) : entry.group ? (
          <div><span className="wl-chip" title="Custom group for this entry">{entry.group}</span></div>
        ) : null}
      </td>
      <td>{editing ? (
        <input
          aria-label="Note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Why is this here?"
        />
      ) : (
        entry.note ?? '—'
      )}</td>
      <td><PriceCell entry={entry} /></td>
      <td><NextStepBadge badge={entry.score} hint="Not yet assessed — open the company, then Score → Assess." /></td>
      <td><NextStepBadge badge={entry.shariah_state} hint="Not screened yet — open the company, then Screening → Run screening." /></td>
      <td>
        {editing ? (
          <input
            aria-label="Thesis link"
            value={thesisLink}
            onChange={(e) => setThesisLink(e.target.value)}
            placeholder="Thesis URL, or leave blank"
          />
        ) : entry.thesis_link && entry.company_ticker ? (
          <>
            <Link to={`/companies/${entry.company_ticker}/thesis`}>Open thesis</Link>
            <div className="muted">
              Validate or invalidate your narrative against the badges in this row —
              a link is context, not advice.
            </div>
          </>
        ) : (
          <NextStepBadge badge={entry.thesis_link_badge} hint="No thesis linked — open the company, then Thesis → Assess." />
        )}
      </td>
      <td>
        {editing ? (
          <>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>{' '}
            <button className="link-btn" onClick={handleCancel} disabled={saving}>
              Cancel
            </button>
          </>
        ) : (
          <>
            <button className="link-btn" onClick={() => setEditing(true)} disabled={busy}>
              Edit
            </button>{' '}
            <button className="link-btn" onClick={handleDelete} disabled={busy}>
              {busy ? 'Removing…' : 'Delete'}
            </button>
          </>
        )}
        {error ? <div className="alert alert-error">{error}</div> : null}
      </td>
    </tr>
  )
})

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : 'Request failed'
}

export default function Watchlists() {
  const queryClient = useQueryClient()
  const {
    data: watchlists,
    isLoading: listsLoading,
    error: listsError,
    refetch: refetchLists,
  } = useWatchlists()

  const [explicitId, setExplicitId] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const [ticker, setTicker] = useState('')
  const [addGroup, setAddGroup] = useState('')
  const [addNote, setAddNote] = useState('')
  const [addThesisLink, setAddThesisLink] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  const { data: companiesPage1 } = useCompanies({ page_size: 200 })
  const { data: companiesPage2 } = useCompanies({ page_size: 200, page: 2 })

  const companyOptions = useMemo(() => {
    const seen = new Map<string, string>()
    for (const page of [companiesPage1, companiesPage2]) {
      for (const c of page?.items ?? []) {
        if (!seen.has(c.ticker)) seen.set(c.ticker, c.name)
      }
    }
    return [...seen.entries()]
      .map(([tick, name]) => ({ ticker: tick, name }))
      .sort((a, b) => a.ticker.localeCompare(b.ticker))
  }, [companiesPage1, companiesPage2])
  const companiesLoading = companiesPage1 === undefined && companiesPage2 === undefined

  // Derived during render (rerender-derived-state-no-effect): no effect needed.
  const lists = watchlists ?? []
  const selected =
    (explicitId ? lists.find((l) => l.id === explicitId) : undefined) ?? lists[0] ?? null
  const selectedId = selected?.id ?? null

  const {
    data: entries,
    isLoading: entriesLoading,
    error: entriesError,
    refetch: refetchEntries,
  } = useWatchlistEntries(selectedId ?? undefined)

  const refreshEntries = async (watchlistId: string): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ['watchlistEntries', watchlistId] })
  }

  const handleCreate = async (): Promise<void> => {
    const name = newName.trim()
    if (name === '') return
    setCreating(true)
    setCreateError(null)
    try {
      const created = await createWatchlist(name)
      await queryClient.invalidateQueries({ queryKey: ['watchlists'] })
      setNewName('')
      setExplicitId(created.id)
      await refetchLists()
    } catch (err) {
      setCreateError(errorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  const handleAdd = async (): Promise<void> => {
    if (!selectedId) return
    const rawTicker = ticker.trim().toUpperCase()
    if (rawTicker === '') return
    setAdding(true)
    setAddError(null)
    try {
      // Resolve the friendly ticker to the internal company id. The API
      // speaks UUIDs; users should never have to.
      let company = null
      try {
        company = await getCompanyByTicker(rawTicker)
      } catch (err) {
        setAddError(err instanceof Error ? err.message : 'Could not look up that ticker.')
        return
      }
      if (!company) {
        setAddError(`No company with ticker "${rawTicker}" — pick one from the list.`)
        return
      }
      await addWatchlistEntry(selectedId, {
        company_id: company.id,
        group: addGroup.trim() === '' ? undefined : addGroup.trim(),
        note: addNote.trim() === '' ? undefined : addNote.trim(),
        thesis_link: addThesisLink.trim() === '' ? undefined : addThesisLink.trim(),
      })
      setTicker('')
      setAddGroup('')
      setAddNote('')
      setAddThesisLink('')
      await refreshEntries(selectedId)
      await refetchEntries()
    } catch (err) {
      setAddError(errorMessage(err))
    } finally {
      setAdding(false)
    }
  }

  if (listsLoading) {
    return <div className="loading">Loading watchlists...</div>
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Watchlists</h1>
          <p className="subtitle">Track groups of companies with server-computed badges per row.</p>
        </div>
      </div>

      {listsError ? (
        <div className="alert alert-error">
          Couldn&apos;t load watchlists.{' '}
          <button className="link-btn" onClick={() => refetchLists()}>
            Retry
          </button>
        </div>
      ) : null}

      <div className="wl-layout">
        <div className="card wl-lists">
          <h2>Lists</h2>
          {lists.length === 0 ? (
            <div className="empty">No watchlists yet. Create your first list below.</div>
          ) : (
            <ul className="wl-list">
              {lists.map((l) => (
                <li key={l.id}>
                  <button
                    className={l.id === selectedId ? 'wl-list-item wl-list-item-active' : 'wl-list-item'}
                    onClick={() => setExplicitId(l.id)}
                  >
                    {l.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="wl-create">
            <input
              aria-label="New list name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="New list name"
            />
            <button
              className="btn btn-primary"
              onClick={handleCreate}
              disabled={creating || newName.trim() === ''}
            >
              {creating ? 'Creating…' : 'Create list'}
            </button>
          </div>
          {createError ? <div className="alert alert-error">{createError}</div> : null}
        </div>

        <div className="wl-entries">
          {selected === null ? (
            <div className="empty">Select or create a list to see its entries.</div>
          ) : entriesLoading ? (
            <div className="loading">Loading entries...</div>
          ) : entriesError ? (
            <div className="alert alert-error">
              Couldn&apos;t load entries for {selected.name}.{' '}
              <button className="link-btn" onClick={() => refetchEntries()}>
                Retry
              </button>
            </div>
          ) : (
            <>
              <div className="card">
                <h2>{selected.name} — add a company</h2>
                <div className="wl-add">
                  <select
                    aria-label="Company ticker"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value)}
                    disabled={adding || companiesLoading}
                  >
                    <option value="">Select a company…</option>
                    {companyOptions.map((c) => (
                      <option key={c.ticker} value={c.ticker}>
                        {c.ticker} — {c.name}
                      </option>
                    ))}
                  </select>
                  <input
                    aria-label="Group"
                    value={addGroup}
                    onChange={(e) => setAddGroup(e.target.value)}
                    placeholder="Group (optional)"
                  />
                  <input
                    aria-label="Note"
                    value={addNote}
                    onChange={(e) => setAddNote(e.target.value)}
                    placeholder="Note (optional)"
                  />
                  <input
                    aria-label="Thesis link"
                    value={addThesisLink}
                    onChange={(e) => setAddThesisLink(e.target.value)}
                    placeholder="Thesis link (optional)"
                  />
                  <button
                    className="btn btn-primary"
                    onClick={handleAdd}
                    disabled={adding || ticker.trim() === ''}
                  >
                    {adding ? 'Adding…' : 'Add entry'}
                  </button>
                </div>
                {addError ? <div className="alert alert-error">{addError}</div> : null}
              </div>

              {(entries ?? []).length === 0 ? (
                <div className="empty">
                  {selected.name} has no entries yet. Add a company above — badges appear
                  once the backend computes them.
                </div>
              ) : (
                <div className="table-container">
                  <table>
                    <caption className="muted">
                      Every badge is server-computed; missing data renders INSUFFICIENT_DATA —
                      never a default, never blank.
                    </caption>
                    <thead>
                      <tr>
                        <th>Company</th>
                        <th>Note</th>
                        <th>Price</th>
                        <th>Score</th>
                        <th>Shariah</th>
                        <th>Thesis</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(entries ?? []).map((entry) => (
                        <EntryRow
                          key={entry.id}
                          entry={entry}
                          watchlistId={selected.id}
                          onChanged={refreshEntries}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <p className="muted">
        Badges are computed server-side per entry; hover a badge for its reason. A stale row
        means its inputs are old — re-check before relying on it. Research context only, not
        investment advice.
      </p>
    </div>
  )
}
