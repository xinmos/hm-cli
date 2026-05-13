from __future__ import annotations

import math
import re
from dataclasses import dataclass

from hermes.core.memory.models import Episode


class BM25Scorer:
    """Zero-dependency BM25 scorer for episode retrieval."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._documents: list[str] = []
        self._doc_lengths: list[int] = []
        self._avgdl: float = 0.0
        self._term_doc_freq: dict[str, int] = {}
        self._term_freqs: list[dict[str, int]] = []
        self._N: int = 0

    def fit(self, documents: list[str]) -> None:
        self._documents = documents
        self._N = len(documents)
        self._doc_lengths = []
        self._term_freqs = []
        self._term_doc_freq = {}

        for doc in documents:
            tokens = self._tokenize(doc)
            self._doc_lengths.append(len(tokens))
            tf: dict[str, int] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            self._term_freqs.append(tf)
            for token in tf:
                self._term_doc_freq[token] = self._term_doc_freq.get(token, 0) + 1

        self._avgdl = sum(self._doc_lengths) / max(1, self._N)

    def score(self, query: str) -> list[float]:
        query_tokens = self._tokenize(query)
        if not query_tokens or self._N == 0:
            return [0.0] * self._N

        scores: list[float] = []
        for i in range(self._N):
            score = 0.0
            doc_len = self._doc_lengths[i]
            tf_map = self._term_freqs[i]
            for token in query_tokens:
                df = self._term_doc_freq.get(token, 0)
                if df == 0:
                    continue
                tf = tf_map.get(token, 0)
                idf = math.log((self._N - df + 0.5) / (df + 0.5) + 1.0)
                numerator = tf * (self._k1 + 1)
                denominator = tf + self._k1 * (1 - self._b + self._b * doc_len / max(1, self._avgdl))
                score += idf * numerator / denominator
            scores.append(score)
        return scores

    def _tokenize(self, text: str) -> list[str]:
        tokens: list[str] = []
        # English words
        tokens.extend(re.findall(r"[a-zA-Z_]\w*", text.lower()))
        # CJK bigrams (pairs of consecutive CJK chars, standard for CJK IR)
        cjk_run: list[str] = []
        for ch in text:
            if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿":
                cjk_run.append(ch)
            else:
                if len(cjk_run) >= 2:
                    tokens.extend("".join(cjk_run[i:i+2]) for i in range(len(cjk_run) - 1))
                elif cjk_run:
                    tokens.extend(cjk_run)
                cjk_run.clear()
        if len(cjk_run) >= 2:
            tokens.extend("".join(cjk_run[i:i+2]) for i in range(len(cjk_run) - 1))
        elif cjk_run:
            tokens.extend(cjk_run)
        return tokens

    @property
    def is_empty(self) -> bool:
        return self._N == 0


@dataclass
class ScoredEpisode:
    episode: Episode
    bm25_score: float
    keyword_score: float
    combined_score: float


def fuse_results(
    episodes: list[Episode],
    bm25_scores: list[float],
    keyword_scores: list[float],
    alpha: float = 0.6,
) -> list[ScoredEpisode]:
    """Weighted fusion of BM25 and keyword match scores (alpha=0.6 gives more weight to BM25)."""
    if not episodes:
        return []

    # Normalize scores to 0-1
    max_bm25 = max(bm25_scores) if bm25_scores else 1.0
    max_kw = max(keyword_scores) if keyword_scores else 1.0

    combined: list[ScoredEpisode] = []
    for i, ep in enumerate(episodes):
        norm_bm25 = bm25_scores[i] / max_bm25 if max_bm25 > 0 else 0.0
        norm_kw = keyword_scores[i] / max_kw if max_kw > 0 else 0.0
        combined_score = alpha * norm_bm25 + (1 - alpha) * norm_kw
        if combined_score > 0:
            combined.append(
                ScoredEpisode(
                    episode=ep,
                    bm25_score=round(norm_bm25, 4),
                    keyword_score=round(norm_kw, 4),
                    combined_score=round(combined_score, 4),
                )
            )

    combined.sort(key=lambda s: s.combined_score, reverse=True)
    return combined
