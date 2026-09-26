"""AI analyzer with source attribution.

Generates analysis from retrieved context while maintaining strict
separation between facts and interpretation. Never invents financial data.
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.document_indexer import DocumentIndexer
from app.ai.rag_pipeline import RAGPipeline, RAGResult
from app.models.ai import AIAnalysis, AnalysisStatusDB, AnalysisTypeDB

logger = logging.getLogger(__name__)


@dataclass
class AnalysisRequest:
    """Request for AI analysis."""
    company_id: uuid.UUID
    analysis_type: AnalysisTypeDB
    query: str
    model_used: str | None = None


@dataclass
class AnalysisResponse:
    """Response from AI analysis."""
    analysis_id: uuid.UUID
    summary: str
    detailed_analysis: str | None
    sources: list[dict]
    confidence_score: float | None
    disclaimer: str
    status: str


class AIAnalyzer:
    """Analyzes financial data with strict source attribution.

    This analyzer uses deterministic rules to synthesize information
    from retrieved context. It never invents financial numbers and
    always distinguishes between facts and interpretation.
    """

    DISCLAIMER = (
        "This analysis is AI-generated based on retrieved financial data. "
        "It should not be considered financial advice. All financial figures "
        "should be verified against original source documents. The analysis "
        "may not reflect the most recent data available."
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.rag = RAGPipeline(session)
        self.indexer = DocumentIndexer(session)

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """Perform AI analysis with source attribution.

        Args:
            request: Analysis request with company ID and type

        Returns:
            AnalysisResponse with sourced analysis
        """
        # Retrieve relevant context
        rag_result = await self.rag.retrieve(
            company_id=request.company_id,
            query=request.query,
            limit=15,
        )

        if not rag_result.chunks:
            return AnalysisResponse(
                analysis_id=uuid.uuid4(),
                summary="Insufficient data available for analysis.",
                detailed_analysis="No relevant financial data was found for this company. "
                    "Please ensure financial statements and metrics have been ingested.",
                sources=[],
                confidence_score=None,
                disclaimer=self.DISCLAIMER,
                status=AnalysisStatusDB.INSUFFICIENT_DATA.value,
            )

        # Generate analysis based on type
        summary, detailed = self._generate_analysis(
            request.analysis_type, rag_result, request.query
        )

        # Extract source citations
        sources = self._extract_sources(rag_result)

        # Calculate confidence based on data availability
        confidence = self._calculate_confidence(rag_result)

        # Persist analysis
        analysis = AIAnalysis(
            company_id=request.company_id,
            analysis_type=request.analysis_type,
            summary=summary,
            detailed_analysis=detailed,
            source_chunk_ids=json.dumps([c.chunk_id for c in rag_result.chunks]),
            confidence_score=confidence,
            disclaimer=self.DISCLAIMER,
            status=AnalysisStatusDB.COMPLETED,
            model_used=request.model_used or "deterministic",
            created_at=datetime.now(UTC),
        )
        self.session.add(analysis)
        await self.session.flush()

        return AnalysisResponse(
            analysis_id=analysis.id,
            summary=summary,
            detailed_analysis=detailed,
            sources=sources,
            confidence_score=confidence,
            disclaimer=self.DISCLAIMER,
            status=AnalysisStatusDB.COMPLETED.value,
        )

    def _generate_analysis(
        self,
        analysis_type: AnalysisTypeDB,
        rag_result: RAGResult,
        query: str,
    ) -> tuple[str, str]:
        """Generate analysis from retrieved context.

        Returns:
            Tuple of (summary, detailed_analysis)
        """
        facts = []
        interpretations = []

        for chunk in rag_result.chunks:
            meta = chunk.metadata
            if chunk.chunk_type == "financial_fact":
                label = meta.get("label", "Unknown")
                value = meta.get("value", "N/A")
                currency = meta.get("currency", "")
                facts.append(f"{label}: {value} {currency}".strip())
            elif chunk.chunk_type == "metric":
                label = meta.get("label", "Unknown")
                value = meta.get("value", "N/A")
                reason = meta.get("reason", "")
                facts.append(f"{label}: {value}")
                if reason:
                    interpretations.append(f"{label}: {reason}")
            elif chunk.chunk_type == "valuation":
                label = meta.get("label", "Unknown")
                value = meta.get("value", "N/A")
                assumptions = meta.get("assumptions", "")
                facts.append(f"{label}: {value}")
                if assumptions:
                    interpretations.append(f"{label} assumptions: {assumptions}")
            elif chunk.chunk_type == "screening":
                label = meta.get("label", "Unknown")
                reason = meta.get("reason", "")
                facts.append(label)
                if reason:
                    interpretations.append(f"Screening rationale: {reason}")

        # Build summary
        summary_parts = []
        if facts:
            summary_parts.append(f"Based on {len(facts)} data points:")
            for fact in facts[:5]:
                summary_parts.append(f"  - {fact}")

        if interpretations:
            summary_parts.append("\nInterpretations:")
            for interp in interpretations[:3]:
                summary_parts.append(f"  - {interp}")

        summary = "\n".join(summary_parts) if summary_parts else "No relevant data found."

        # Build detailed analysis
        detailed_parts = [
            f"Analysis Type: {analysis_type.value}",
            f"Data Sources: {len(rag_result.chunks)} chunks retrieved",
            f"Query: {query}",
            "",
            "Facts (from verified data):",
        ]
        for fact in facts:
            detailed_parts.append(f"  - {fact}")

        if interpretations:
            detailed_parts.append("")
            detailed_parts.append("Interpretations (AI-generated):")
            for interp in interpretations:
                detailed_parts.append(f"  - {interp}")

        detailed_parts.append("")
        detailed_parts.append("Note: Financial figures are from source data. "
            "Interpretations are AI-generated and should be verified.")

        return summary, "\n".join(detailed_parts)

    def _extract_sources(self, rag_result: RAGResult) -> list[dict]:
        """Extract source citations from retrieved chunks."""
        sources = []
        for i, chunk in enumerate(rag_result.chunks, 1):
            sources.append({
                "citation": f"[{i}]",
                "chunk_type": chunk.chunk_type,
                "content_preview": chunk.content[:200],
                "relevance_score": round(chunk.score, 3),
                "metadata": chunk.metadata,
            })
        return sources

    def _calculate_confidence(self, rag_result: RAGResult) -> float:
        """Calculate confidence score based on data availability."""
        if not rag_result.chunks:
            return 0.0

        # More chunks and higher scores = higher confidence
        avg_score = sum(c.score for c in rag_result.chunks) / len(rag_result.chunks)
        chunk_factor = min(len(rag_result.chunks) / 10, 1.0)

        return round(avg_score * chunk_factor, 4)
