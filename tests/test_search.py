"""Tests for search module."""

from __future__ import annotations

from pathlib import Path

from claude_reflections.indexer import IndexableMessage
from claude_reflections.search import EmbeddingManager, SearchResult, SqliteVecManager


class TestEmbeddingManager:
    """Tests for EmbeddingManager."""

    def test_embed_single(self) -> None:
        """Should generate embedding for single text."""
        text = "How do I fix a Docker memory issue?"
        embedding = EmbeddingManager.embed(text)

        assert isinstance(embedding, list)
        assert len(embedding) == 384  # all-MiniLM-L6-v2 dimension
        assert all(isinstance(x, float) for x in embedding)

    def test_embed_batch(self) -> None:
        """Should generate embeddings for multiple texts."""
        texts = ["First text", "Second text", "Third text"]
        embeddings = EmbeddingManager.embed_batch(texts)

        assert len(embeddings) == 3
        assert all(len(e) == 384 for e in embeddings)

    def test_embed_batch_empty(self) -> None:
        """Empty batch should return empty list."""
        embeddings = EmbeddingManager.embed_batch([])
        assert embeddings == []

    def test_similar_texts_have_similar_embeddings(self) -> None:
        """Similar texts should have similar embeddings."""
        import math

        def cosine_similarity(a: list[float], b: list[float]) -> float:
            dot_product = sum(x * y for x, y in zip(a, b, strict=True))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            return dot_product / (norm_a * norm_b)

        text1 = "How to fix Docker memory problems"
        text2 = "Docker memory issue solutions"
        text3 = "Python list comprehension tutorial"

        emb1 = EmbeddingManager.embed(text1)
        emb2 = EmbeddingManager.embed(text2)
        emb3 = EmbeddingManager.embed(text3)

        sim_12 = cosine_similarity(emb1, emb2)
        sim_13 = cosine_similarity(emb1, emb3)

        # Similar texts should have higher similarity
        assert sim_12 > sim_13


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_creation(self) -> None:
        """Should create search result with all fields."""
        result = SearchResult(
            uuid="test-uuid",
            file_path="/path/to/file.jsonl",
            line_number=42,
            role="user",
            snippet="This is a test...",
            score=0.85,
            timestamp="2025-01-15T10:00:00Z",
            session_id="session-123",
        )

        assert result.uuid == "test-uuid"
        assert result.line_number == 42
        assert result.score == 0.85


class TestIndexableMessage:
    """Tests for IndexableMessage dataclass."""

    def test_creation(self) -> None:
        """Should create indexable message with all fields."""
        msg = IndexableMessage(
            uuid="msg-001",
            role="user",
            content="Test content",
            timestamp="2025-01-15T10:00:00Z",
            session_id="session-123",
            file_path="/path/to/file.jsonl",
            line_number=10,
            byte_offset=500,
        )

        assert msg.uuid == "msg-001"
        assert msg.role == "user"
        assert msg.content == "Test content"


class TestSqliteVecManager:
    """Tests for SqliteVecManager."""

    def test_ensure_collection(self, tmp_path: Path) -> None:
        """Should create table if not exists."""
        manager = SqliteVecManager(tmp_path / "vectors.db")
        manager.ensure_collection()
        stats = manager.get_collection_stats()
        assert stats["status"] == "ok"
        assert stats["points_count"] == 0
        manager.close()

    def test_index_and_search(self, tmp_path: Path) -> None:
        """Should index messages and search them."""
        manager = SqliteVecManager(tmp_path / "vectors.db")

        messages = [
            IndexableMessage(
                uuid="test-001",
                role="user",
                content="How do I configure Docker containers?",
                timestamp="2025-01-15T10:00:00Z",
                session_id="session-test",
                file_path="/test/file.jsonl",
                line_number=1,
                byte_offset=0,
            ),
        ]

        count = manager.index_messages(messages)
        assert count == 1

        results = manager.search("Docker configuration")
        assert len(results) > 0
        assert results[0].uuid == "test-001"
        manager.close()

    def test_get_collection_stats(self, tmp_path: Path) -> None:
        """Should return correct stats."""
        manager = SqliteVecManager(tmp_path / "vectors.db")

        # No table yet
        stats = manager.get_collection_stats()
        assert stats["status"] == "not_found"
        assert stats["points_count"] == 0

        # Create and index
        messages = [
            IndexableMessage(
                uuid=f"test-{i:03d}",
                role="user",
                content=f"Test message number {i}",
                timestamp="2025-01-15T10:00:00Z",
                session_id="session-test",
                file_path="/test/file.jsonl",
                line_number=i,
                byte_offset=i * 100,
            )
            for i in range(3)
        ]
        manager.index_messages(messages)

        stats = manager.get_collection_stats()
        assert stats["status"] == "ok"
        assert stats["points_count"] == 3
        manager.close()

    def test_drop_collection(self, tmp_path: Path) -> None:
        """Should drop and allow recreation."""
        manager = SqliteVecManager(tmp_path / "vectors.db")

        messages = [
            IndexableMessage(
                uuid="test-001",
                role="user",
                content="Test content",
                timestamp="2025-01-15T10:00:00Z",
                session_id="session-test",
                file_path="/test/file.jsonl",
                line_number=1,
                byte_offset=0,
            ),
        ]
        manager.index_messages(messages)

        stats = manager.get_collection_stats()
        assert stats["points_count"] == 1

        manager.drop_collection()

        stats = manager.get_collection_stats()
        assert stats["status"] == "not_found"
        assert stats["points_count"] == 0

        # Re-index after drop
        manager.index_messages(messages)
        stats = manager.get_collection_stats()
        assert stats["points_count"] == 1
        manager.close()

    def test_search_score_threshold(self, tmp_path: Path) -> None:
        """Should filter results below score threshold."""
        manager = SqliteVecManager(tmp_path / "vectors.db")

        messages = [
            IndexableMessage(
                uuid="test-001",
                role="user",
                content="How do I configure Docker containers?",
                timestamp="2025-01-15T10:00:00Z",
                session_id="session-test",
                file_path="/test/file.jsonl",
                line_number=1,
                byte_offset=0,
            ),
        ]
        manager.index_messages(messages)

        # Very high threshold should return fewer or no results
        results_high = manager.search("completely unrelated quantum physics", score_threshold=0.9)
        results_low = manager.search("Docker configuration", score_threshold=0.1)

        # Low threshold query about Docker should return our Docker message
        assert len(results_low) > 0
        # High threshold with unrelated query should return fewer results
        assert len(results_high) <= len(results_low)
        manager.close()

    def test_empty_index(self, tmp_path: Path) -> None:
        """Should return empty results from empty index."""
        manager = SqliteVecManager(tmp_path / "vectors.db")
        manager.ensure_collection()

        results = manager.search("anything")
        assert results == []
        manager.close()

    def test_index_empty_messages(self, tmp_path: Path) -> None:
        """Should handle empty message list."""
        manager = SqliteVecManager(tmp_path / "vectors.db")
        count = manager.index_messages([])
        assert count == 0
        manager.close()
