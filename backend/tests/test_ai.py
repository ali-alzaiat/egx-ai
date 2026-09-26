"""Tests for AI analysis and RAG pipeline."""

import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.analyzer import AIAnalyzer, AnalysisRequest
from app.ai.document_indexer import DocumentIndexer
from app.ai.rag_pipeline import RAGPipeline
from app.models.ai import AnalysisStatusDB, AnalysisTypeDB, ChunkTypeDB, DocumentChunk


class TestDocumentIndexer:
    """Tests for document indexing."""

    @pytest.mark.asyncio
    async def test_indexer_initializes(self, db_session: AsyncSession) -> None:
        indexer = DocumentIndexer(db_session)
        assert indexer.session == db_session

    @pytest.mark.asyncio
    async def test_index_company_returns_counts(self, db_session: AsyncSession, test_company) -> None:
        indexer = DocumentIndexer(db_session)
        counts = await indexer.index_company(test_company.id)
        assert isinstance(counts, dict)
        assert "financial_facts" in counts
        assert "financial_metrics" in counts
        assert "valuations" in counts
        assert "screenings" in counts


class TestRAGPipeline:
    """Tests for RAG retrieval."""

    @pytest.mark.asyncio
    async def test_rag_retrieves_empty_when_no_chunks(self, db_session: AsyncSession, test_company) -> None:
        rag = RAGPipeline(db_session)
        result = await rag.retrieve(test_company.id, "test query")
        assert result.chunks == []
        assert result.total_chunks_searched == 0

    @pytest.mark.asyncio
    async def test_rag_retrieves_relevant_chunks(self, db_session: AsyncSession, test_company) -> None:
        chunk1 = DocumentChunk(
            company_id=test_company.id,
            chunk_type=ChunkTypeDB.FINANCIAL_FACT,
            content="Revenue: 1000000 EGP income statement",
            metadata_json=json.dumps({"label": "Revenue", "value": "1000000"}),
        )
        chunk2 = DocumentChunk(
            company_id=test_company.id,
            chunk_type=ChunkTypeDB.METRIC,
            content="P/E Ratio: 15.5 metric valuation",
            metadata_json=json.dumps({"label": "P/E Ratio", "value": "15.5"}),
        )
        db_session.add_all([chunk1, chunk2])
        await db_session.flush()

        rag = RAGPipeline(db_session)
        result = await rag.retrieve(test_company.id, "revenue income")

        assert len(result.chunks) > 0
        assert result.total_chunks_searched == 2

    @pytest.mark.asyncio
    async def test_rag_disclaimer_present(self, db_session: AsyncSession, test_company) -> None:
        rag = RAGPipeline(db_session)
        result = await rag.retrieve(test_company.id, "query")
        assert "financial data" in result.disclaimer.lower() or "source" in result.disclaimer.lower()


class TestAIAnalyzer:
    """Tests for AI analysis with source attribution."""

    @pytest.mark.asyncio
    async def test_analyzer_returns_insufficient_data_when_no_chunks(
        self, db_session: AsyncSession, test_company
    ) -> None:
        analyzer = AIAnalyzer(db_session)
        result = await analyzer.analyze(AnalysisRequest(
            company_id=test_company.id,
            analysis_type=AnalysisTypeDB.COMPANY_SYNTHESIS,
            query="Summarize financial health",
        ))

        assert result.status == AnalysisStatusDB.INSUFFICIENT_DATA.value
        assert result.disclaimer != ""

    @pytest.mark.asyncio
    async def test_analyzer_generates_analysis_with_chunks(
        self, db_session: AsyncSession, test_company
    ) -> None:
        chunk = DocumentChunk(
            company_id=test_company.id,
            chunk_type=ChunkTypeDB.FINANCIAL_FACT,
            content="Revenue: 5000000 EGP",
            metadata_json=json.dumps({"label": "Revenue", "value": "5000000", "currency": "EGP"}),
        )
        db_session.add(chunk)
        await db_session.flush()

        analyzer = AIAnalyzer(db_session)
        result = await analyzer.analyze(AnalysisRequest(
            company_id=test_company.id,
            analysis_type=AnalysisTypeDB.COMPANY_SYNTHESIS,
            query="Analyze revenue",
        ))

        assert result.status == AnalysisStatusDB.COMPLETED.value
        assert len(result.sources) > 0
        assert result.confidence_score is not None
        assert result.disclaimer != ""

    @pytest.mark.asyncio
    async def test_analysis_distinguishes_facts_from_interpretation(
        self, db_session: AsyncSession, test_company
    ) -> None:
        chunk = DocumentChunk(
            company_id=test_company.id,
            chunk_type=ChunkTypeDB.METRIC,
            content="ROE: 12.5% - Above industry average",
            metadata_json=json.dumps({
                "label": "ROE",
                "value": "12.5%",
                "reason": "Above industry average of 10%",
            }),
        )
        db_session.add(chunk)
        await db_session.flush()

        analyzer = AIAnalyzer(db_session)
        result = await analyzer.analyze(AnalysisRequest(
            company_id=test_company.id,
            analysis_type=AnalysisTypeDB.METRIC_EXPLANATION,
            query="Explain ROE",
        ))

        assert "Facts" in result.detailed_analysis or "facts" in result.detailed_analysis.lower()
        assert "Interpretation" in result.detailed_analysis or "interpretation" in result.detailed_analysis.lower()

    @pytest.mark.asyncio
    async def test_analysis_never_invents_financial_numbers(
        self, db_session: AsyncSession, test_company
    ) -> None:
        chunk = DocumentChunk(
            company_id=test_company.id,
            chunk_type=ChunkTypeDB.FINANCIAL_FACT,
            content="Net Income: 2000000 EGP",
            metadata_json=json.dumps({"label": "Net Income", "value": "2000000"}),
        )
        db_session.add(chunk)
        await db_session.flush()

        analyzer = AIAnalyzer(db_session)
        result = await analyzer.analyze(AnalysisRequest(
            company_id=test_company.id,
            analysis_type=AnalysisTypeDB.COMPANY_SYNTHESIS,
            query="What is the net income?",
        ))

        assert "2000000" in result.summary or "insufficient" in result.summary.lower()


class TestAnalysisTypes:
    """Tests for analysis type validation."""

    def test_all_analysis_types_exist(self) -> None:
        assert AnalysisTypeDB.COMPANY_SYNTHESIS.value == "company_synthesis"
        assert AnalysisTypeDB.DOCUMENT_SUMMARY.value == "document_summary"
        assert AnalysisTypeDB.METRIC_EXPLANATION.value == "metric_explanation"
        assert AnalysisTypeDB.SCREENING_EXPLANATION.value == "screening_explanation"
        assert AnalysisTypeDB.VALUATION_EXPLANATION.value == "valuation_explanation"

    def test_chunk_types_exist(self) -> None:
        assert ChunkTypeDB.FINANCIAL_FACT.value == "financial_fact"
        assert ChunkTypeDB.METRIC.value == "metric"
        assert ChunkTypeDB.VALUATION.value == "valuation"
        assert ChunkTypeDB.SCREENING.value == "screening"
        assert ChunkTypeDB.DOCUMENT_TEXT.value == "document_text"
