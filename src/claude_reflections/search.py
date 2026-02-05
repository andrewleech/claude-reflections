"""Vector search with Qdrant and FastEmbed embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PointStruct, VectorParams

from .config import get_qdrant_url
from .indexer import IndexableMessage

# Default embedding model (384 dimensions)
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


@dataclass
class SearchResult:
    """A search result with file reference."""

    uuid: str
    file_path: str
    line_number: int
    role: str
    snippet: str
    score: float
    timestamp: str
    session_id: str


class EmbeddingManager:
    """Manages embedding generation with FastEmbed."""

    _instance: TextEmbedding | None = None

    @classmethod
    def get_model(cls) -> TextEmbedding:
        """Get or create the embedding model (singleton)."""
        if cls._instance is None:
            cls._instance = TextEmbedding(model_name=EMBEDDING_MODEL)
        return cls._instance

    @classmethod
    def embed(cls, text: str) -> list[float]:
        """Generate embedding for a single text."""
        model = cls.get_model()
        embeddings = list(model.embed([text]))
        return embeddings[0].tolist()

    @classmethod
    def embed_batch(cls, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []
        model = cls.get_model()
        return [e.tolist() for e in model.embed(texts)]


class QdrantManager:
    """Manages Qdrant operations for a project."""

    def __init__(
        self,
        collection_name: str,
        qdrant_url: str | None = None,
    ) -> None:
        self.collection_name = collection_name
        self.qdrant_url = qdrant_url or get_qdrant_url()
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        """Get or create the Qdrant client."""
        if self._client is None:
            self._client = QdrantClient(url=self.qdrant_url)
        return self._client

    def ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )

    def index_messages(self, messages: list[IndexableMessage]) -> int:
        """Index a batch of messages. Returns count indexed."""
        if not messages:
            return 0

        self.ensure_collection()

        # Generate embeddings
        texts = [msg.content[:2000] for msg in messages]  # Truncate for embedding
        embeddings = EmbeddingManager.embed_batch(texts)

        # Create points
        points: list[PointStruct] = []
        for msg, embedding in zip(messages, embeddings, strict=True):
            # Create snippet for display
            snippet = msg.content[:300]
            if len(msg.content) > 300:
                snippet += "..."

            point = PointStruct(
                id=msg.uuid,
                vector=embedding,
                payload={
                    "file_path": msg.file_path,
                    "line_number": msg.line_number,
                    "uuid": msg.uuid,
                    "role": msg.role,
                    "snippet": snippet,
                    "timestamp": msg.timestamp,
                    "session_id": msg.session_id,
                },
            )
            points.append(point)

        # Upsert in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )

        return len(points)

    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.3,
    ) -> list[SearchResult]:
        """Search for messages matching a query."""
        # Check if collection exists
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            return []

        # Generate query embedding
        query_embedding = EmbeddingManager.embed(query)

        # Search using new query_points API
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=limit,
            score_threshold=score_threshold,
        )

        # Convert to SearchResult
        search_results: list[SearchResult] = []
        for hit in response.points:
            payload: dict[str, Any] = hit.payload or {}
            search_results.append(
                SearchResult(
                    uuid=payload.get("uuid", ""),
                    file_path=payload.get("file_path", ""),
                    line_number=payload.get("line_number", 0),
                    role=payload.get("role", ""),
                    snippet=payload.get("snippet", ""),
                    score=hit.score,
                    timestamp=payload.get("timestamp", ""),
                    session_id=payload.get("session_id", ""),
                )
            )

        return search_results

    def get_collection_stats(self) -> dict[str, Any]:
        """Get statistics about the collection."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "collection": self.collection_name,
                "points_count": info.points_count or 0,
                "status": str(info.status),
            }
        except UnexpectedResponse:
            # Collection doesn't exist
            return {
                "collection": self.collection_name,
                "points_count": 0,
                "status": "not_found",
            }
