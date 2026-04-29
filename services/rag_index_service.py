import hashlib
import logging
import math
import re
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional

from flask import current_app

from models import Transcript

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qdrant_models
except Exception:  # pragma: no cover - optional dependency
    QdrantClient = None
    qdrant_models = None

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except Exception:  # pragma: no cover - optional dependency
    RecursiveCharacterTextSplitter = None


logger = logging.getLogger(__name__)


class HashingEmbeddingService:
    """Small local embedding fallback so Qdrant can work without another API."""

    def __init__(self, vector_size: int):
        self.vector_size = vector_size

    def embed(self, text: str) -> List[float]:
        tokens = re.findall(r"[a-zA-Z0-9]{2,}", (text or "").lower())
        if not tokens:
            return [0.0] * self.vector_size

        counter = Counter(tokens)
        vector = [0.0] * self.vector_size

        for token, count in counter.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.vector_size
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * (1.0 + math.log(count))

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector


class RagIndexService:
    def __init__(self):
        self._client: Optional[QdrantClient] = None
        self._embedder: Optional[HashingEmbeddingService] = None

    def is_configured(self) -> bool:
        return bool(current_app.config.get("QDRANT_URL")) and QdrantClient is not None and qdrant_models is not None

    def is_available(self) -> bool:
        return self.is_configured()

    def get_client(self) -> Optional[QdrantClient]:
        if not self.is_configured():
            return None
        if self._client is None:
            self._client = QdrantClient(
                url=current_app.config.get("QDRANT_URL"),
                api_key=current_app.config.get("QDRANT_API_KEY") or None,
                timeout=10.0,
            )
        return self._client

    def get_embedder(self) -> HashingEmbeddingService:
        if self._embedder is None:
            self._embedder = HashingEmbeddingService(
                vector_size=current_app.config.get("QDRANT_VECTOR_SIZE", 256)
            )
        return self._embedder

    def ensure_collection(self) -> bool:
        client = self.get_client()
        if client is None:
            return False

        collection = current_app.config.get("QDRANT_COLLECTION")
        vector_size = current_app.config.get("QDRANT_VECTOR_SIZE", 256)

        try:
            existing = {item.name for item in client.get_collections().collections}
            if collection not in existing:
                client.create_collection(
                    collection_name=collection,
                    vectors_config=qdrant_models.VectorParams(
                        size=vector_size,
                        distance=qdrant_models.Distance.COSINE,
                    ),
                )
            return True
        except Exception as error:
            logger.warning("Qdrant collection setup failed: %s", error)
            return False

    def index_transcript(self, transcript: Transcript) -> bool:
        client = self.get_client()
        if client is None or not self.ensure_collection():
            logger.warning(
                "Skipping transcript %s indexing because Qdrant client/collection is unavailable",
                getattr(transcript, "id", "unknown"),
            )
            return False

        chunks = self._build_chunks(transcript)
        if not chunks:
            logger.warning("Transcript %s produced 0 chunks for Qdrant indexing", transcript.id)
            return False

        collection = current_app.config.get("QDRANT_COLLECTION")
        embedder = self.get_embedder()

        try:
            self.delete_transcript_chunks(transcript_id=transcript.id, user_id=transcript.user_id)
            points = []
            for index, chunk in enumerate(chunks):
                payload = {
                    "user_id": transcript.user_id,
                    "transcript_id": transcript.id,
                    "title": transcript.title or transcript.filename,
                    "filename": transcript.filename,
                    "chunk_index": index,
                    "chunk_text": chunk["chunk_text"],
                    "speaker": chunk.get("speaker"),
                    "start_time": chunk.get("start_time"),
                    "end_time": chunk.get("end_time"),
                    "source_kind": "transcript",
                    "created_at": transcript.created_at.isoformat() if transcript.created_at else None,
                }
                points.append(
                    qdrant_models.PointStruct(
                        id=self._chunk_point_id(transcript.id, index),
                        vector=embedder.embed(chunk["chunk_text"]),
                        payload=payload,
                    )
                )

            client.upsert(collection_name=collection, points=points, wait=True)
            logger.info(
                "Indexed transcript %s into Qdrant collection '%s' with %s chunks",
                transcript.id,
                collection,
                len(points),
            )
            return True
        except Exception as error:
            logger.warning("Failed to index transcript %s into Qdrant: %s", transcript.id, error)
            return False

    def delete_transcript_chunks(self, *, transcript_id: int, user_id: int) -> bool:
        client = self.get_client()
        if client is None:
            return False

        collection = current_app.config.get("QDRANT_COLLECTION")
        try:
            client.delete(
                collection_name=collection,
                points_selector=qdrant_models.FilterSelector(
                    filter=qdrant_models.Filter(
                        must=[
                            qdrant_models.FieldCondition(
                                key="user_id",
                                match=qdrant_models.MatchValue(value=user_id),
                            ),
                            qdrant_models.FieldCondition(
                                key="transcript_id",
                                match=qdrant_models.MatchValue(value=transcript_id),
                            ),
                        ]
                    )
                ),
                wait=True,
            )
            return True
        except Exception as error:
            logger.warning("Failed deleting transcript %s chunks from Qdrant: %s", transcript_id, error)
            return False

    def search_chunks(
        self,
        *,
        user_id: int,
        question: str,
        transcript_id: Optional[int],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        client = self.get_client()
        if client is None or not self.ensure_collection():
            return []

        collection = current_app.config.get("QDRANT_COLLECTION")
        query_vector = self.get_embedder().embed(question)
        conditions = [
            qdrant_models.FieldCondition(
                key="user_id",
                match=qdrant_models.MatchValue(value=user_id),
            )
        ]
        if transcript_id is not None:
            conditions.append(
                qdrant_models.FieldCondition(
                    key="transcript_id",
                    match=qdrant_models.MatchValue(value=transcript_id),
                )
            )

        try:
            results = client.search(
                collection_name=collection,
                query_vector=query_vector,
                query_filter=qdrant_models.Filter(must=conditions),
                limit=top_k,
                with_payload=True,
            )
        except Exception as error:
            logger.warning("Qdrant search failed, falling back to DB retrieval: %s", error)
            return []

        chunks: List[Dict[str, Any]] = []
        for result in results:
            payload = result.payload or {}
            chunks.append(
                {
                    "transcript_id": payload.get("transcript_id"),
                    "title": payload.get("title") or "Transcript",
                    "chunk_text": payload.get("chunk_text") or "",
                    "score": float(result.score),
                    "speaker": payload.get("speaker"),
                    "start_time": payload.get("start_time"),
                    "end_time": payload.get("end_time"),
                    "source_kind": payload.get("source_kind") or "transcript",
                }
            )
        return chunks

    def reindex_user_transcripts(self, user_id: int) -> Dict[str, int]:
        transcripts = Transcript.query.filter_by(user_id=user_id).all()
        indexed = 0
        failed = 0
        for transcript in transcripts:
            if self.index_transcript(transcript):
                indexed += 1
            else:
                failed += 1
        return {"indexed": indexed, "failed": failed, "total": len(transcripts)}

    def _build_chunks(self, transcript: Transcript) -> List[Dict[str, Any]]:
        transcript_data = transcript.transcript_data or {}
        segments = transcript_data.get("segments") or transcript_data.get("speaker_segments") or []

        if segments:
            grouped_chunks: List[Dict[str, Any]] = []
            current_words = 0
            current_texts: List[str] = []
            current_speaker = None
            current_start = None
            current_end = None
            max_words = current_app.config.get("RAG_CHUNK_WORDS", 120)

            for segment in segments:
                text = (segment.get("text") or "").strip()
                if not text:
                    continue
                words = text.split()

                if current_texts and current_words + len(words) > max_words:
                    grouped_chunks.append(
                        {
                            "chunk_text": " ".join(current_texts),
                            "speaker": current_speaker,
                            "start_time": current_start,
                            "end_time": current_end,
                        }
                    )
                    current_words = 0
                    current_texts = []
                    current_speaker = None
                    current_start = None
                    current_end = None

                current_texts.append(text)
                current_words += len(words)
                current_speaker = current_speaker or segment.get("speaker")
                current_start = segment.get("start") if current_start is None else current_start
                current_end = segment.get("end")

            if current_texts:
                grouped_chunks.append(
                    {
                        "chunk_text": " ".join(current_texts),
                        "speaker": current_speaker,
                        "start_time": current_start,
                        "end_time": current_end,
                    }
                )

            if grouped_chunks:
                return grouped_chunks

        full_text = transcript_data.get("text") or transcript_data.get("full_text") or ""
        return self._split_text_chunks(full_text)

    def _split_text_chunks(self, text: str) -> List[Dict[str, Any]]:
        text = (text or "").strip()
        if not text:
            return []

        if RecursiveCharacterTextSplitter is not None:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=current_app.config.get("RAG_CHUNK_WORDS", 120) * 6,
                chunk_overlap=current_app.config.get("RAG_CHUNK_OVERLAP", 30) * 6,
            )
            return [{"chunk_text": chunk} for chunk in splitter.split_text(text) if chunk.strip()]

        words = text.split()
        chunk_size = current_app.config.get("RAG_CHUNK_WORDS", 120)
        overlap = current_app.config.get("RAG_CHUNK_OVERLAP", 30)
        step = max(1, chunk_size - overlap)
        chunks = []
        for index in range(0, len(words), step):
            part = words[index:index + chunk_size]
            if part:
                chunks.append({"chunk_text": " ".join(part)})
        return chunks

    def _chunk_point_id(self, transcript_id: int, chunk_index: int) -> str:
        raw_id = f"transcript-{transcript_id}-chunk-{chunk_index}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, raw_id))


rag_index_service = RagIndexService()
