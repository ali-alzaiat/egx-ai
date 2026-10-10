import "./AIInsights.css";

import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useCompanyByTicker } from '../api/client'
import CompanyNotFound from '../components/CompanyNotFound'
import CompanyTabs from '../components/CompanyTabs'

const ANALYSIS_TYPES = [
  { value: 'company_synthesis', label: 'Company Synthesis' },
  { value: 'document_summary', label: 'Document Summary' },
  { value: 'metric_explanation', label: 'Metric Explanation' },
  { value: 'screening_explanation', label: 'Screening Explanation' },
  { value: 'valuation_explanation', label: 'Valuation Explanation' },
]

interface AnalysisResult {
  analysis_id: string
  summary: string
  detailed_analysis: string | null
  sources: {
    citation: string
    chunk_type: string
    content_preview: string
    relevance_score: number
    metadata: Record<string, unknown>
  }[]
  confidence_score: number | null
  disclaimer: string
  status: string
}

export default function AIInsights() {
  const { ticker } = useParams<{ ticker: string }>()
  const { data: company, isLoading: companyLoading, error: companyError } = useCompanyByTicker(ticker)

  const [analysisType, setAnalysisType] = useState('company_synthesis')
  const [query, setQuery] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isPreparing, setIsPreparing] = useState(false)
  const [prepareMsg, setPrepareMsg] = useState<string | null>(null)
  const [prepareEmpty, setPrepareEmpty] = useState(false)
  const [prepareError, setPrepareError] = useState<string | null>(null)

  const handleAnalyze = async () => {
    if (!company || !query) return

    setIsAnalyzing(true)
    setError(null)

    try {
      const res = await fetch(`/api/ai/companies/${company.id}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis_type: analysisType, query }),
      })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const data = await res.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handlePrepare = async () => {
    if (!company) return

    setIsPreparing(true)
    setPrepareMsg(null)
    setPrepareEmpty(false)
    setPrepareError(null)
    try {
      const res = await fetch(`/api/ai/companies/${company.id}/index`, {
        method: 'POST',
      })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const data = await res.json()
      const n = Number(data.total_chunks ?? 0)
      if (n > 0) {
        setPrepareMsg(`Prepared ${n} data items for ${company.ticker}.`)
      } else {
        setPrepareEmpty(true)
      }
    } catch (err) {
      setPrepareError(err instanceof Error ? err.message : 'Preparation failed')
    } finally {
      setIsPreparing(false)
    }
  }

  if (companyLoading) return <div className="loading">Loading company...</div>
  if (companyError || !company) return <CompanyNotFound ticker={ticker} />

  return (
    <div className="page">
      <div className="page-header">
        <h1>AI Insights — {company.ticker}</h1>
        <p style={{ color: 'var(--text-secondary)' }}>{company.name}</p>
      </div>

      <CompanyTabs ticker={company.ticker} />

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ margin: 0 }}>Prepare data for analysis</h3>
          <button
            className="btn btn-secondary"
            onClick={handlePrepare}
            disabled={isPreparing}
          >
            {isPreparing ? 'Prepare data…' : 'Prepare data'}
          </button>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          Gather this company's financial facts, metrics, valuations, and
          screening results so analysis has something to work with.
        </p>
        {prepareMsg && <p role="status">{prepareMsg}</p>}
        {prepareEmpty && (
          <div className="alert alert-warning">Nothing to prepare yet</div>
        )}
        {prepareError && (
          <div className="alert alert-error">
            {prepareError}{' '}
            <button className="link-btn" onClick={handlePrepare}>
              Retry
            </button>
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ marginBottom: '1rem' }}>Run Analysis</h3>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>
            Analysis Type
          </label>
          <select
            value={analysisType}
            onChange={(e) => setAnalysisType(e.target.value)}
            style={{ width: '100%', padding: '0.5rem' }}
          >
            {ANALYSIS_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>
            Query
          </label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. Summarize the company's financial health based on available data"
            rows={3}
            style={{ width: '100%', padding: '0.5rem', boxSizing: 'border-box' }}
          />
        </div>

        {error && (
          <div style={{ color: 'var(--color-negative)', marginBottom: '1rem' }}>{error}</div>
        )}

        <button
          className="btn btn-primary"
          onClick={handleAnalyze}
          disabled={isAnalyzing || !query}
        >
          {isAnalyzing ? 'Analyzing...' : 'Run Analysis'}
        </button>
      </div>

      {result && (
        <>
          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <h3 style={{ marginBottom: '0.5rem' }}>Analysis Result</h3>
            <div style={{
              padding: '0.75rem',
              background: 'var(--bg-secondary)',
              borderRadius: '6px',
              marginBottom: '1rem',
              whiteSpace: 'pre-wrap',
            }}>
              {result.summary}
            </div>

            {result.confidence_score !== null && (
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Confidence: {(result.confidence_score * 100).toFixed(1)}%
              </p>
            )}

            <div style={{
              padding: '0.75rem',
              background: 'var(--bg-tertiary, #f0f0f0)',
              borderRadius: '6px',
              fontSize: '0.75rem',
              color: 'var(--text-secondary)',
              marginTop: '1rem',
            }}>
              {result.disclaimer}
            </div>
          </div>

          {result.detailed_analysis && (
            <div className="card" style={{ marginBottom: '1.5rem' }}>
              <h3 style={{ marginBottom: '0.5rem' }}>Detailed Analysis</h3>
              <pre style={{
                whiteSpace: 'pre-wrap',
                fontSize: '0.875rem',
                lineHeight: '1.6',
                margin: 0,
              }}>
                {result.detailed_analysis}
              </pre>
            </div>
          )}

          {result.sources.length > 0 && (
            <div className="card">
              <h3 style={{ marginBottom: '0.5rem' }}>Sources</h3>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Citation</th>
                      <th>Type</th>
                      <th>Content</th>
                      <th>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.sources.map((src) => (
                      <tr key={src.citation}>
                        <td>{src.citation}</td>
                        <td>{src.chunk_type}</td>
                        <td style={{ maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {src.content_preview}
                        </td>
                        <td>{(src.relevance_score * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
