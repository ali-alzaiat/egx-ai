# Phase 8 — AI Analyst & RAG

## Objective
Implement AI as an interpretation layer over verified financial data.

## Scope
- Document ingestion and indexing (RAG)
- AI analysis of financial documents
- Company analysis synthesis
- Source attribution for AI outputs
- API endpoints for AI analysis
- Frontend AI insights display

## Dependencies
Phase 3 — Financial Statements must be complete.
Phase 4 — Financial Metrics should be complete.
Phase 5 — Shariah Screening should be complete.

## Requirements
1. Document ingestion for annual reports, quarterly reports
2. Vector embeddings for document retrieval (pgvector)
3. RAG pipeline: retrieve relevant context → generate analysis
4. AI analysis must:
   - Cite sources for all claims
   - Distinguish facts from interpretations
   - Not invent financial numbers
   - Use verified data from Phase 3-4
5. Company analysis synthesis from multiple sources
6. API endpoints: analyze document, get analysis, company insights
7. Frontend: AI insights display with source links

## Acceptance Criteria
- AI analysis includes source citations
- Financial numbers in AI output match verified data
- Clear distinction between facts and AI interpretation
- RAG retrieves relevant document sections
- No hallucinated financial values

## Required Tests
- RAG retrieval returns relevant context
- AI analysis includes citations
- Financial numbers match source data
- Edge cases: insufficient documents, missing data

## Required Verification
```bash
pytest
ruff check
mypy
curl http://localhost:8000/api/ai/companies/{id}/analysis
```

## Explicitly Forbidden Features
- No AI-generated financial numbers
- No "BUY" or "SELL" recommendations
- No predictions without uncertainty
- No fabricated sources

## Expected Deliverables
- `backend/app/ai/document_indexer.py` — document indexing
- `backend/app/ai/rag_pipeline.py` — RAG retrieval
- `backend/app/ai/analyzer.py` — AI analysis
- `backend/app/models/ai.py` — AIAnalysis, DocumentChunk
- `backend/app/api/ai.py`
- `frontend/src/pages/AIInsights.tsx`
- Migration for AI tables
- Documentation of AI limitations

## Special Review Requirements
This phase requires extra architectural review:
- AI must never be the source of financial truth
- All AI outputs must cite sources
- Hallucination controls must be implemented
- Clear separation between facts and interpretation
