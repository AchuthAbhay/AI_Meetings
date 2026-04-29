import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from flask import current_app

from models import Summary, Transcript
from services.rag_index_service import rag_index_service

try:
    from groq import Groq
except Exception:  # pragma: no cover - optional at runtime
    Groq = None

logger = logging.getLogger(__name__)

# Basic stop words to make the local keyword fallback slightly smarter
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", 
    "has", "he", "in", "is", "it", "its", "of", "on", "that", "the", 
    "to", "was", "were", "will", "with"
}

@dataclass
class RetrievedChunk:
    transcript_id: int
    title: str
    chunk_text: str
    score: float
    speaker: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    source_kind: str = "transcript"

    def to_source(self) -> Dict[str, Any]:
        source = {
            "transcript_id": self.transcript_id,
            "title": self.title,
            "chunk_text": self.chunk_text,
            "score": round(self.score, 4),
            "source_kind": self.source_kind,
        }
        if self.speaker:
            source["speaker"] = self.speaker
        if self.start_time is not None:
            source["start_time"] = self.start_time
        if self.end_time is not None:
            source["end_time"] = self.end_time
        return source


class ChatService:
    """RAG-oriented chat service with a local retrieval fallback."""

    def answer_question(
        self,
        *,
        user_id: int,
        question: str,
        scope: str = "all",
        transcript_id: Optional[int] = None,
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        question = (question or "").strip()
        if not question:
            return {
                "success": False,
                "error": "Question is required.",
            }

        effective_top_k = top_k or current_app.config.get("RAG_TOP_K", 5)
        
        # Retrieve chunks (tries Qdrant first, then local DB)
        retrieved = self._retrieve_chunks(
            user_id=user_id,
            question=question,
            scope=scope,
            transcript_id=transcript_id,
            top_k=effective_top_k,
        )
        
        retrieval_mode = "qdrant" if rag_index_service.is_available() and retrieved else "local"

        if not retrieved:
            return {
                "success": True,
                "answer": "I could not find enough relevant transcript context to answer that yet.",
                "sources": [],
                "retrieval_mode": retrieval_mode,
            }

        answer = self._generate_answer(question=question, chunks=retrieved)
        return {
            "success": True,
            "answer": answer,
            "sources": [chunk.to_source() for chunk in retrieved],
            "retrieval_mode": retrieval_mode,
        }

    def _retrieve_chunks(
        self,
        *,
        user_id: int,
        question: str,
        scope: str,
        transcript_id: Optional[int],
        top_k: int,
    ) -> List[RetrievedChunk]:
        # 1. Try Qdrant First
        qdrant_hits = self._retrieve_qdrant_chunks(
            user_id=user_id,
            question=question,
            transcript_id=transcript_id,
            top_k=top_k,
        )
        if qdrant_hits:
            return qdrant_hits

        # 2. Database Fallback (Strictly respects transcript_id if provided)
        transcripts_query = Transcript.query.filter_by(user_id=user_id)
        if transcript_id:
            transcripts_query = transcripts_query.filter_by(id=transcript_id)

        transcripts = transcripts_query.order_by(Transcript.created_at.desc()).limit(50).all()
        query_terms = self._tokenize(question)
        scored_chunks: List[RetrievedChunk] = []

        for transcript in transcripts:
            scored_chunks.extend(self._score_transcript_chunks(transcript, query_terms))

        # Include saved summaries if searching globally, UNLESS a specific transcript is targeted
        if scope != "current" and not transcript_id:
            scored_chunks.extend(self._score_summary_chunks(user_id=user_id, query_terms=query_terms))

        scored_chunks.sort(key=lambda item: item.score, reverse=True)
        return [chunk for chunk in scored_chunks[:top_k] if chunk.score > 0]

    def _retrieve_qdrant_chunks(
        self,
        *,
        user_id: int,
        question: str,
        transcript_id: Optional[int],
        top_k: int,
    ) -> List[RetrievedChunk]:
        if not rag_index_service.is_available():
            return []

        # Force use the transcript_id if provided (Simplified Logic)
        hits = rag_index_service.search_chunks(
            user_id=user_id,
            question=question,
            transcript_id=transcript_id,
            top_k=top_k,
        )
        return [
            RetrievedChunk(
                transcript_id=hit.get("transcript_id") or 0,
                title=hit.get("title") or "Transcript",
                chunk_text=hit.get("chunk_text") or "",
                score=float(hit.get("score") or 0.0),
                speaker=hit.get("speaker"),
                start_time=hit.get("start_time"),
                end_time=hit.get("end_time"),
                source_kind=hit.get("source_kind") or "transcript",
            )
            for hit in hits
            if hit.get("chunk_text")
        ]

    def _score_transcript_chunks(self, transcript: Transcript, query_terms: List[str]) -> List[RetrievedChunk]:
        chunks = self._extract_transcript_chunks(transcript)
        scored: List[RetrievedChunk] = []

        for chunk in chunks:
            score = self._score_text(query_terms, chunk["chunk_text"], transcript.title or transcript.filename)
            if score <= 0:
                continue

            scored.append(
                RetrievedChunk(
                    transcript_id=transcript.id,
                    title=transcript.title or transcript.filename,
                    chunk_text=chunk["chunk_text"],
                    score=score,
                    speaker=chunk.get("speaker"),
                    start_time=chunk.get("start_time"),
                    end_time=chunk.get("end_time"),
                    source_kind="transcript",
                )
            )

        return scored

    def _score_summary_chunks(self, *, user_id: int, query_terms: List[str]) -> List[RetrievedChunk]:
        summaries = (
            Summary.query.filter_by(user_id=user_id)
            .order_by(Summary.created_at.desc())
            .limit(20)
            .all()
        )
        scored: List[RetrievedChunk] = []

        for summary in summaries:
            score = self._score_text(query_terms, summary.content or "", summary.title or "Summary")
            if score <= 0:
                continue

            scored.append(
                RetrievedChunk(
                    transcript_id=summary.transcript_id or 0,
                    title=summary.title or "Summary",
                    chunk_text=(summary.content or "")[:700],
                    score=score * 0.9,
                    source_kind="summary",
                )
            )

        return scored

    def _extract_transcript_chunks(self, transcript: Transcript) -> List[Dict[str, Any]]:
        transcript_data = transcript.transcript_data or {}
        segments = transcript_data.get("segments") or transcript_data.get("speaker_segments") or []
        if segments:
            chunks = []
            for segment in segments:
                text = (segment.get("text") or "").strip()
                if not text:
                    continue
                chunks.append(
                    {
                        "chunk_text": text,
                        "speaker": segment.get("speaker"),
                        "start_time": segment.get("start"),
                        "end_time": segment.get("end"),
                    }
                )
            if chunks:
                return chunks

        full_text = transcript_data.get("text") or self._join_transcript_segments(transcript_data.get("segments") or [])
        return self._chunk_plain_text(full_text or "")

    def _chunk_plain_text(self, text: str) -> List[Dict[str, Any]]:
        # Slightly improved chunking logic
        words = text.split()
        if not words:
            return []

        chunk_size = current_app.config.get("RAG_CHUNK_WORDS", 120)
        overlap = current_app.config.get("RAG_CHUNK_OVERLAP", 30)
        chunks: List[Dict[str, Any]] = []
        step = max(1, chunk_size - overlap)

        for index in range(0, len(words), step):
            chunk_words = words[index:index + chunk_size]
            if not chunk_words:
                continue
            chunks.append({"chunk_text": " ".join(chunk_words)})

        return chunks

    def _join_transcript_segments(self, segments: List[Dict[str, Any]]) -> str:
        return " ".join((segment.get("text") or "").strip() for segment in segments if segment.get("text"))

    def _score_text(self, query_terms: List[str], body: str, title: str) -> float:
        body_terms = self._tokenize(body)
        if not body_terms:
            return 0.0

        body_counter = Counter(body_terms)
        title_terms = set(self._tokenize(title))
        overlap = sum(min(body_counter.get(term, 0), 3) for term in set(query_terms))
        title_bonus = sum(1 for term in set(query_terms) if term in title_terms)

        norm = math.log(len(body_terms) + 10, 10)
        return (overlap + (title_bonus * 1.5)) / max(norm, 1.0)

    def _tokenize(self, text: str) -> List[str]:
        # Improved: filters out basic stop words
        tokens = re.findall(r"[a-zA-Z0-9]{2,}", (text or "").lower())
        return [t for t in tokens if t not in STOP_WORDS]

    def _generate_answer(self, *, question: str, chunks: List[RetrievedChunk]) -> str:
        groq_answer = self._generate_answer_with_groq(question=question, chunks=chunks)
        if groq_answer:
            return groq_answer
        return self._generate_fallback_answer(question=question, chunks=chunks)

    def _generate_answer_with_groq(self, *, question: str, chunks: List[RetrievedChunk]) -> Optional[str]:
        api_key = current_app.config.get("GROQ_API_KEY")
        if not api_key or Groq is None:
            return None

        try:
            client = Groq(api_key=api_key)
            model = current_app.config.get("GROQ_CHAT_MODEL", "llama-3.1-8b-instant")
            context = "\n\n".join(
                f"Source: {chunk.title}\n"
                f"Speaker: {chunk.speaker or 'Unknown'}\n"
                f"Excerpt: {chunk.chunk_text}"
                for chunk in chunks
            )

            completion = client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an AI analyst for meeting transcripts and related knowledge. "
                            "Answer only from the supplied context. If context is insufficient, say so clearly. "
                            "Keep answers concise, practical, and business-ready."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Question:\n{question}\n\nRetrieved context:\n{context}",
                    },
                ],
            )
            return completion.choices[0].message.content.strip()
        except Exception as error:
            logger.warning("Groq chat generation failed, using fallback answer: %s", error)
            return None

    def _generate_fallback_answer(self, *, question: str, chunks: List[RetrievedChunk]) -> str:
        lines = [
            "Here is the most relevant context I found for your question:",
            "",
        ]

        for index, chunk in enumerate(chunks[:3], start=1):
            source_bits = [chunk.title]
            if chunk.speaker:
                source_bits.append(f"speaker {chunk.speaker}")
            if chunk.start_time is not None:
                source_bits.append(f"{chunk.start_time:.1f}s")

            excerpt = chunk.chunk_text.strip()
            if len(excerpt) > 260:
                excerpt = excerpt[:257] + "..."

            lines.append(f"{index}. {' | '.join(source_bits)}")
            lines.append(excerpt)
            lines.append("")

        lines.append(
            "This is a retrieval fallback response. Once Groq and Qdrant are fully wired, this endpoint can return a more synthesized answer."
        )
        return "\n".join(lines).strip()

chat_service = ChatService()