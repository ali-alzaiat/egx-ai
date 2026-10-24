import "./Valuation.css";

import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { calculateValuations, useCompanyByTicker, useFairValue, useValuations } from '../api/client'
import CompanyNotFound from '../components/CompanyNotFound'
import FairValueCard from '../components/FairValueCard'
import SensitivityTable from '../components/SensitivityTable'
import type { CompanyValuation } from '../types'

// Assumption groups for the calculate form (query-param names match
// POST /api/valuation/companies/{id}/calculate).
const GROUPS: { title: string; fields: { key: string; label: string }[] }[] = [
  {
    title: 'P/E',
    fields: [
      { key: 'earnings_per_share', label: 'Earnings per share' },
      { key: 'pe_ratio', label: 'P/E ratio' },
    ],
  },
  {
    title: 'P/B',
    fields: [
      { key: 'book_value_per_share', label: 'Book value per share' },
      { key: 'pb_ratio', label: 'P/B ratio' },
    ],
  },
  {
    title: 'EV/EBITDA',
    fields: [
      { key: 'ebitda', label: 'EBITDA' },
      { key: 'ev_ebitda_ratio', label: 'EV/EBITDA multiple' },
      { key: 'net_debt', label: 'Net debt' },
    ],
  },
  {
    title: 'DCF',
    fields: [
      { key: 'free_cash_flow', label: 'Free cash flow' },
      { key: 'growth_rate', label: 'Growth rate' },
      { key: 'discount_rate', label: 'Discount rate' },
      { key: 'terminal_growth_rate', label: 'Terminal growth rate' },
    ],
  },
  {
    title: 'Shared',
    fields: [{ key: 'shares_outstanding', label: 'Shares outstanding' }],
  },
]

function statusWord(status: string): string {
  if (status === 'AVAILABLE') return 'Available'
  if (status === 'INVALID') return 'Invalid inputs'
  return 'Not enough data'
}

export default function Valuation() {
  const { ticker } = useParams<{ ticker: string }>()
  const queryClient = useQueryClient()
  const { data: company, isLoading: companyLoading, error: companyError } = useCompanyByTicker(ticker)
  const {
    data: valuations,
    isLoading: valuationsLoading,
    error: valuationsError,
    refetch,
  } = useValuations(company?.id)
  const {
    data: fairValue,
    isLoading: fvLoading,
    error: fvError,
    refetch: refetchFv,
  } = useFairValue(company?.id)

  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const setInput = (key: string, value: string): void => {
    setInputs((prev) => ({ ...prev, [key]: value }))
  }

  const handleCalculate = async (): Promise<void> => {
    if (!company) return
    setRunning(true)
    setRunError(null)
    setToast(null)
    try {
      const params: Record<string, number | undefined> = {}
      for (const [key, raw] of Object.entries(inputs)) {
        if (raw.trim() === '') continue
        const n = Number(raw)
        params[key] = Number.isFinite(n) ? n : undefined
      }
      const res = await calculateValuations(company.id, params)
      await queryClient.invalidateQueries({ queryKey: ['valuations'] })
      await queryClient.invalidateQueries({ queryKey: ['fairValue'] })
      await refetch()
      await refetchFv()
      const evaluated = res.valuations.filter((v) => v.status === 'AVAILABLE').length
      setToast(`Valuation updated — ${evaluated} evaluated`)
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Valuation failed')
    } finally {
      setRunning(false)
    }
  }

  if (companyLoading || valuationsLoading || fvLoading) {
    return <div className="loading">Loading company...</div>
  }

  if (companyError || !company) {
    return <CompanyNotFound ticker={ticker} />
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Valuation - {company.ticker}</h2>
          <p className="subtitle">{company.name}</p>
        </div>
        <button className="btn btn-primary" onClick={handleCalculate} disabled={running}>
          {running ? 'Calculating…' : 'Calculate valuation'}
        </button>
      </div>


      <div className="valuation-info">
        <p>
          <strong>Note:</strong> Valuations are based on explicit assumptions
          and deterministic formulas. Results should be interpreted with
          understanding of the underlying assumptions.
        </p>
      </div>

      {toast && (
        <p role="status" className="muted">{toast}</p>
      )}
      {runError && (
        <div className="alert alert-error">
          {runError}{' '}
          <button className="link-btn" onClick={handleCalculate}>
            Retry
          </button>
        </div>
      )}
      {valuationsError && (
        <div className="alert alert-error">
          Couldn't load valuations.{' '}
          <button className="link-btn" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      <div className="card">
        <h2 className="section-title">Assumptions</h2>
        <p className="muted">The app does not hold analyst estimates — supply the assumptions you want to test.</p>
        {GROUPS.map((group) => (
          <fieldset key={group.title}>
            <legend>{group.title}</legend>
            {group.fields.map((field) => (
              <label key={field.key}>
                {field.label}
                <input
                  type="number"
                  step="any"
                  value={inputs[field.key] ?? ''}
                  onChange={(e) => setInput(field.key, e.target.value)}
                  className="filter-input"
                />
              </label>
            ))}
          </fieldset>
        ))}
      </div>

      {valuations && valuations.length > 0 && (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Value</th>
                <th>Status</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {valuations.map((v: CompanyValuation) => (
                <tr key={v.id ?? v.model}>
                  <td>{v.model}</td>
                  <td>{v.value ?? '—'}</td>
                  <td>{statusWord(v.status)}</td>
                  <td>{v.reason ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {fvError ? (
        <div className="alert alert-error">
          Couldn't load the weighted fair value.{' '}
          <button className="link-btn" onClick={() => refetchFv()}>
            Retry
          </button>
        </div>
      ) : fairValue ? (
        <>
          <FairValueCard fairValue={fairValue} />
          <SensitivityTable
            rows={fairValue.sensitivity}
            baseValue={fairValue.fair_value.value}
          />
        </>
      ) : (
        <div className="empty">
          No weighted fair value computed yet. It appears here once calculated —
          always paired with its assumptions.
        </div>
      )}
    </div>
  )
}
