import './Watchlists.css'

import { memo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  addWatchlistEntry,
  createWatchlist,
  deleteWatchlistEntry,
  updateWatchlistEntry,
  useWatchlistEntries,
  useWatchlists,
} from '../api/client'
import type { PhaseBadge, WatchlistEntry } from '../types'

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
    if (!window.confirm(`Remove ${entry.company_ticker ?? entry.company_id} from this list?`)) return
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
        <strong>{entry.company_ticker ?? entry.company_id}</strong>
        {entry.company_name ? <div className="muted">{entry.company_name}</div> : null}
      </td>
      <td>{editing ? (
        <input
          aria-label="Group"
          value={group}
          onChange={(e) => setGroup(e.target.value)}
          placeholder="e.g. banks"
        />
      ) : (
        entry.group ?? '—'
      )}</td>
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
      <td>
        {editing ? (
          <input
            aria-label="Thesis link"
            value={thesisLink}
            onChange={(e) => setThesisLink(e.target.value)}
            placeholder="thesis id or url"
          />
        ) : entry.thesis_link ? (
          <>
            <span>{entry.thesis_link}</span>
            <div className="muted">
              Validate or invalidate your narrative against the badges in this row —
              a link is context, not advice.
            </div>
          </>
        ) : (
          '—'
        )}
      </td>
      <td><EntryBadge badge={entry.price} /></td>
      <td><EntryBadge badge={entry.change} /></td>
      <td><EntryBadge badge={entry.as_of} /></td>
      <td><EntryBadge badge={entry.staleness} /></td>
      <td><EntryBadge badge={entry.score} /></td>
      <td><EntryBadge badge={entry.shariah_state} /></td>
      <td><EntryBadge badge={entry.thesis_link_badge} /></td>
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

  const [companyId, setCompanyId] = useState('')
  const [addGroup, setAddGroup] = useState('')
  const [addNote, setAddNote] = useState('')
  const [addThesisLink, setAddThesisLink] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

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
    const id = companyId.trim()
    if (id === '') return
    setAdding(true)
    setAddError(null)
    try {
      await addWatchlistEntry(selectedId, {
        company_id: id,
        group: addGroup.trim() === '' ? undefined : addGroup.trim(),
        note: addNote.trim() === '' ? undefined : addNote.trim(),
        thesis_link: addThesisLink.trim() === '' ? undefined : addThesisLink.trim(),
      })
      setCompanyId('')
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
                  <input
                    aria-label="Company ID"
                    value={companyId}
                    onChange={(e) => setCompanyId(e.target.value)}
                    placeholder="Company ID (required)"
                  />
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
                    disabled={adding || companyId.trim() === ''}
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
                        <th>Group</th>
                        <th>Note</th>
                        <th>Thesis link</th>
                        <th>Price</th>
                        <th>Change</th>
                        <th>Data as of</th>
                        <th>Staleness</th>
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
