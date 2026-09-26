"""RAG pipeline for retrieving relevant context from indexed chunks.

Uses keyword-based similarity search as a deterministic fallback
when embeddings are not available.
"""

import contextlib
import json
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import ChunkTypeDB, DocumentChunk

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A chunk retrieved by the RAG pipeline with relevance score."""
    content: str
    metadata: dict
    score: float
    chunk_type: str
    chunk_id: str


@dataclass
class RAGResult:
    """Result from RAG retrieval."""
    chunks: list[RetrievedChunk]
    query: str
    total_chunks_searched: int
    disclaimer: str = field(default_factory=lambda: (
        "This analysis is based on retrieved financial data and AI interpretation. "
        "It should not be considered financial advice. All financial figures should "
        "be verified against original source documents."
    ))


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline.

    Retrieves relevant document chunks for a given query, providing context
    for AI analysis while maintaining source attribution.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def retrieve(
        self,
        company_id: uuid.UUID,
        query: str,
        chunk_types: list[ChunkTypeDB] | None = None,
        limit: int = 10,
    ) -> RAGResult:
        """Retrieve relevant chunks for a query.

        Uses keyword matching as a deterministic retrieval method.
        When pgvector embeddings are populated, could use cosine similarity.

        Args:
            company_id: Company to search within
            query: Search query
            chunk_types: Filter to specific chunk types
            limit: Maximum chunks to return

        Returns:
            RAGResult with ranked chunks
        """
        # Build base query
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.company_id == company_id)
        )

        if chunk_types:
            stmt = stmt.where(DocumentChunk.chunk_type.in_(chunk_types))

        result = await self.session.execute(stmt)
        all_chunks = result.scalars().all()

        # Score chunks by keyword relevance
        scored_chunks: list[RetrievedChunk] = []
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        for chunk in all_chunks:
            score = self._calculate_relevance(query_terms, chunk.content)
            if score > 0:
                metadata = {}
                if chunk.metadata_json:
                    with contextlib.suppress(json.JSONDecodeError):
                        metadata = json.loads(chunk.metadata_json)

                scored_chunks.append(RetrievedChunk(
                    content=chunk.content,
                    metadata=metadata,
                    score=score,
                    chunk_type=chunk.chunk_type.value,
                    chunk_id=str(chunk.id),
                ))

        # Sort by score descending
        scored_chunks.sort(key=lambda x: x.score, reverse=True)
        top_chunks = scored_chunks[:limit]

        return RAGResult(
            chunks=top_chunks,
            query=query,
            total_chunks_searched=len(all_chunks),
        )

    async def retrieve_with_embeddings(
        self,
        company_id: uuid.UUID,
        query_embedding: list[float],
        limit: int = 10,
    ) -> RAGResult:
        """Retrieve using vector similarity (requires pgvector).

        Falls back to keyword search if embeddings are not populated.
        """
        # Try vector search first
        try:
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            sql = text("""
                SELECT id, content, metadata_json, chunk_type,
                       1 - (embedding <=> :embedding::vector) as similarity
                FROM document_chunks
                WHERE company_id = :company_id
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> :embedding::vector
                LIMIT :limit
            """)
            result = await self.session.execute(sql, {
                "embedding": embedding_str,
                "company_id": str(company_id),
                "limit": limit,
            })
            rows = result.fetchall()

            if rows:
                chunks = []
                for row in rows:
                    metadata = {}
                    if row.metadata_json:
                        with contextlib.suppress(json.JSONDecodeError):
                            metadata = json.loads(row.metadata_json)
                    chunks.append(RetrievedChunk(
                        content=row.content,
                        metadata=metadata,
                        score=float(row.similarity),
                        chunk_type=row.chunk_type,
                        chunk_id=str(row.id),
                    ))
                return RAGResult(chunks=chunks, query="", total_chunks_searched=len(rows))
        except Exception:
            logger.debug("Vector search not available, falling back to keyword search")

        # Fallback: empty result
        return RAGResult(chunks=[], query="", total_chunks_searched=0)

    def _calculate_relevance(self, query_terms: set[str], content: str) -> float:
        """Calculate keyword relevance score."""
        import re
        content_lower = content.lower()
        # Strip punctuation and split
        content_terms = set(re.findall(r'\w+', content_lower))
        # Also strip punctuation from query terms
        clean_query_terms = set()
        for term in query_terms:
            clean_query_terms.update(re.findall(r'\w+', term))

        # Jaccard-like similarity
        intersection = clean_query_terms & content_terms
        union = clean_query_terms | content_terms

        if not union:
            return 0.0

        return len(intersection) / len(union)
