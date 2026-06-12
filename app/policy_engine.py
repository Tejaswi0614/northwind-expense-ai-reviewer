from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class PolicyChunk:
    document: str
    title: str
    text: str


class PolicyLibrary:
    def __init__(self, policy_dir: Path):
        self.policy_dir = policy_dir
        self.chunks = self._load_chunks()

        if self.chunks:
            self.vectorizer = TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2)
            )
            self.matrix = self.vectorizer.fit_transform(
                [chunk.text for chunk in self.chunks]
            )
        else:
            self.vectorizer = None
            self.matrix = None

    def _read_pdf(self, path: Path) -> str:
        reader = PdfReader(str(path))
        pages = []

        for page in reader.pages:
            pages.append(page.extract_text() or "")

        return "\n".join(pages)

    def _load_chunks(self) -> list[PolicyChunk]:
        chunks: list[PolicyChunk] = []

        for pdf in sorted(self.policy_dir.glob("*.pdf")):
            text = self._read_pdf(pdf)

            title = next(
                (line.strip() for line in text.splitlines() if line.strip()),
                pdf.stem
            )

            sections = re.split(
                r"\n(?=\d+(?:\.\d+)*\.\s|[A-Z][A-Za-z &]+ Policy\n|Document:\s)",
                text
            )

            for section in sections:
                clean_text = re.sub(r"\s+", " ", section).strip()

                if len(clean_text) >= 120:
                    chunks.append(
                        PolicyChunk(
                            document=pdf.name,
                            title=title,
                            text=clean_text[:1300]
                        )
                    )

        return chunks

    def search(self, query: str, limit: int = 4) -> list[tuple[PolicyChunk, float]]:
        if not self.chunks or self.matrix is None or self.vectorizer is None:
            return []

        query_vector = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self.matrix).ravel()

        ranked_indexes = scores.argsort()[::-1][:limit]

        results: list[tuple[PolicyChunk, float]] = []

        for index in ranked_indexes:
            score = float(scores[index])

            if score > 0:
                results.append((self.chunks[index], score))

        return results

    def answer_question(self, question: str) -> dict:
        hits = self.search(question, limit=3)

        if not hits or hits[0][1] < 0.08:
            return {
                "answer": (
                    "I could not find enough support in the Northwind policy "
                    "library to answer that safely."
                ),
                "citations": [],
                "confidence": 0.0,
            }

        citations = []

        for chunk, score in hits:
            citations.append(
                {
                    "document": chunk.document,
                    "quote": chunk.text[:650],
                    "score": round(score, 3),
                }
            )

        answer_points = []

        for citation in citations:
            first_sentences = citation["quote"].split(". ")[:2]
            answer_points.append(" ".join(first_sentences).strip())

        answer = "Based on the policy library:\n\n" + "\n\n".join(answer_points)

        return {
            "answer": answer,
            "citations": citations,
            "confidence": round(hits[0][1], 2),
        }