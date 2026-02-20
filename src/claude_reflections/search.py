"""Vector search with sqlite-vec and FastEmbed embeddings."""

from __future__ import annotations

import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlite_vec
from fastembed import TextEmbedding

from .indexer import IndexableMessage

# Default embedding model (384 dimensions)
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Fixed table name used in every per-project DB
TABLE_NAME = "vectors"


def serialize_f32(v: list[float]) -> bytes:
    """Serialize a float vector to bytes for sqlite-vec."""
    return struct.pack(f"{len(v)}f", *v)


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


class SqliteVecManager:
    """Manages sqlite-vec operations for a project."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create the SQLite connection."""
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn

    def ensure_collection(self) -> None:
        """Create vector table if it doesn't exist."""
        self.conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS "{TABLE_NAME}" USING vec0(
                embedding float[{EMBEDDING_DIM}] distance_metric=cosine,
                +uuid TEXT,
                +file_path TEXT,
                +line_number INTEGER,
                +role TEXT,
                +snippet TEXT,
                +timestamp TEXT,
                +session_id TEXT
            )
        """)

    def index_messages(self, messages: list[IndexableMessage]) -> int:
        """Index a batch of messages. Returns count indexed."""
        if not messages:
            return 0

        self.ensure_collection()

        # Generate embeddings
        texts = [msg.content[:2000] for msg in messages]  # Truncate for embedding
        embeddings = EmbeddingManager.embed_batch(texts)

        # Insert rows
        for msg, embedding in zip(messages, embeddings, strict=True):
            snippet = msg.content[:300]
            if len(msg.content) > 300:
                snippet += "..."

            self.conn.execute(
                f"""
                INSERT INTO "{TABLE_NAME}"(
                    embedding, uuid, file_path, line_number,
                    role, snippet, timestamp, session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    serialize_f32(embedding),
                    msg.uuid,
                    msg.file_path,
                    msg.line_number,
                    msg.role,
                    snippet,
                    msg.timestamp,
                    msg.session_id,
                ),
            )

        self.conn.commit()
        return len(messages)

    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.3,
    ) -> list[SearchResult]:
        """Search for messages matching a query."""
        # Check if table exists
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (TABLE_NAME,),
        )
        if cursor.fetchone() is None:
            return []

        # Generate query embedding
        query_embedding = EmbeddingManager.embed(query)

        # Search using vec0 MATCH
        rows = self.conn.execute(
            f"""
            SELECT
                distance,
                uuid,
                file_path,
                line_number,
                role,
                snippet,
                timestamp,
                session_id
            FROM "{TABLE_NAME}"
            WHERE embedding MATCH ?
                AND k = ?
            """,
            (serialize_f32(query_embedding), limit),
        ).fetchall()

        # Convert to SearchResult, filtering by threshold
        results: list[SearchResult] = []
        for row in rows:
            distance = row[0]
            similarity = 1.0 - distance
            if similarity < score_threshold:
                continue
            results.append(
                SearchResult(
                    uuid=row[1],
                    file_path=row[2],
                    line_number=row[3],
                    role=row[4],
                    snippet=row[5],
                    score=similarity,
                    timestamp=row[6],
                    session_id=row[7],
                )
            )

        return results

    def get_collection_stats(self) -> dict[str, Any]:
        """Get statistics about the collection."""
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (TABLE_NAME,),
        )
        if cursor.fetchone() is None:
            return {
                "points_count": 0,
                "status": "not_found",
            }

        count = self.conn.execute(f'SELECT count(*) FROM "{TABLE_NAME}"').fetchone()[0]
        return {
            "points_count": count,
            "status": "ok",
        }

    def drop_collection(self) -> None:
        """Drop the vector table."""
        self.conn.execute(f'DROP TABLE IF EXISTS "{TABLE_NAME}"')
        self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
