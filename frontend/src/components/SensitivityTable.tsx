import { memo } from 'react'
import type { FairValueResponse } from '../types'

// 1-D sensitivity around the base case, always rendered next to the fair
// value (frontend-catchup-contract Batch A.3): a table when the backend has
// rows, an honest note when it has none (nothing is assumed).

type SensitivityRow = FairValueResponse['sensitivity'][number]

const PARAM_LABEL: Record<string, string> = {
  discount_rate: 'Discount rate',
  revenue_growth: 'Revenue growth',
}

function paramLabel(row: SensitivityRow): string {
  const raw =
    typeof row.parameter === 'string' && row.parameter !== ''
      ? row.parameter
      : (row.discount_delta ?? row.discount) !== null &&
          (row.discount_delta ?? row.discount) !== undefined
        ? 'discount_rate'
        : 'revenue_growth'
  return PARAM_LABEL[raw] ?? raw.replace(/_/g, ' ')
}

function cell(row: SensitivityRow, keys: string[]): string {
  for (const key of keys) {
    const v = row[key]
    if (v !== null && v !== undefined && v !== '') return String(v)
  }
  return '—'
}

function SensitivityTable({
  rows,
  baseValue,
}: {
  rows: SensitivityRow[]
  baseValue: string | null
}) {
  if (rows.length === 0) {
    return (
      <div className="card">
        <h2 className="section-title">Sensitivity</h2>
        <p className="muted">
          No sensitivity rows: the backend needs a discount rate and revenue
          growth to perturb, and nothing is assumed. Base fair value:{' '}
          {baseValue ?? '—'}.
        </p>
      </div>
    )
  }
  return (
    <div className="card">
      <h2 className="section-title">Sensitivity</h2>
      <p className="muted">
        One input moved at a time around the base case (base fair value:{' '}
        {baseValue ?? '—'}).
      </p>
      <div className="table-container">
        <table>
          <caption className="muted">
            How the fair value moves when one assumption moves
          </caption>
          <thead>
            <tr>
              <th scope="col">Parameter</th>
              <th scope="col">Assumption value</th>
              <th scope="col">Fair value</th>
              <th scope="col">Change vs base</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                <td>{paramLabel(row)}</td>
                <td>
                  {cell(row, [
                    'value',
                    'discount_delta',
                    'growth_delta',
                    'discount',
                    'growth',
                  ])}
                </td>
                <td>{cell(row, ['fair_value', 'value'])}</td>
                <td>{cell(row, ['change_from_base'])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default memo(SensitivityTable)
