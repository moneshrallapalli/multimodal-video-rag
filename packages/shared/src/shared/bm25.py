"""Pure-Python BM25 sparse encoder for Pinecone hybrid search.

Pinecone serverless hybrid search expects sparse vectors as `{indices, values}` —
this module produces those without pulling in `pinecone-text` (NLTK + tokenizers,
~50 MB cold-start overhead on Lambda).

Usage:
    encoder = BM25Encoder.fit(["chunk one text", "chunk two text", ...])
    sparse = encoder.encode_document("a transcript chunk")     # at upsert time
    sparse = encoder.encode_query("user search query")         # at query time
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# Hash the token to a fixed sparse index. We keep the modulus large enough that
# collisions are negligible for any realistic transcript-chunk vocabulary.
_HASH_VOCAB_SIZE = 2**20  # ≈ 1M slots

# Standard BM25 hyperparameters; documented defaults from the original paper.
_DEFAULT_K1 = 1.2
_DEFAULT_B = 0.75

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "as",
        "by",
        "at",
        "from",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "i",
        "you",
        "she",
        "he",
        "they",
        "we",
        "do",
        "does",
        "did",
        "doing",
    }
)


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN_RE.findall(text.lower())
        if len(token) > 2 and token not in _STOPWORDS
    ]


def _hash_index(token: str) -> int:
    # Stable, deterministic hash without relying on Python's PYTHONHASHSEED.
    h = 0xCBF29CE484222325  # FNV-1a 64-bit offset
    for byte in token.encode("utf-8"):
        h ^= byte
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h % _HASH_VOCAB_SIZE


@dataclass
class BM25Encoder:
    """Document-frequency-aware sparse encoder.

    Persist `.to_dict()` to S3 after fitting and reload with `from_dict()` for
    query-time use without re-reading the corpus.
    """

    avgdl: float
    doc_freq: dict[str, int]
    n_docs: int
    k1: float = _DEFAULT_K1
    b: float = _DEFAULT_B
    vocab_size: int = field(default=_HASH_VOCAB_SIZE)

    @classmethod
    def fit(
        cls, documents: list[str], *, k1: float = _DEFAULT_K1, b: float = _DEFAULT_B
    ) -> BM25Encoder:
        if not documents:
            return cls(avgdl=0.0, doc_freq={}, n_docs=0, k1=k1, b=b)
        doc_freq: dict[str, int] = {}
        total_length = 0
        for doc in documents:
            tokens = _tokens(doc)
            total_length += len(tokens)
            for term in set(tokens):
                doc_freq[term] = doc_freq.get(term, 0) + 1
        return cls(
            avgdl=total_length / len(documents),
            doc_freq=doc_freq,
            n_docs=len(documents),
            k1=k1,
            b=b,
        )

    # ── Encoding ──────────────────────────────────────────────────────

    def encode_document(self, text: str) -> dict[str, list[int] | list[float]]:
        """Sparse representation suitable for `vectors[].sparse_values` on upsert.

        Uses per-term tf with length normalization (the BM25 document side).
        """
        tokens = _tokens(text)
        if not tokens or self.n_docs == 0:
            return {"indices": [], "values": []}
        doc_len = len(tokens)
        tf = Counter(tokens)
        denom_norm = 1.0 - self.b + self.b * (doc_len / max(self.avgdl, 1.0))
        indices: list[int] = []
        values: list[float] = []
        for term, freq in tf.items():
            weight = (freq * (self.k1 + 1.0)) / (freq + self.k1 * denom_norm)
            indices.append(_hash_index(term))
            values.append(weight)
        return {"indices": indices, "values": values}

    def encode_query(self, text: str) -> dict[str, list[int] | list[float]]:
        """Sparse representation suitable for `query.sparse_vector`.

        Uses per-term idf so rare terms dominate (the BM25 query side).
        """
        tokens = _tokens(text)
        if not tokens or self.n_docs == 0:
            return {"indices": [], "values": []}
        seen = Counter(tokens)
        indices: list[int] = []
        values: list[float] = []
        for term, freq in seen.items():
            df = self.doc_freq.get(term, 0)
            # Robertson-Sparck-Jones idf with the +1 smoothing.
            idf = math.log(1.0 + (self.n_docs - df + 0.5) / (df + 0.5))
            if idf <= 0:
                continue
            indices.append(_hash_index(term))
            values.append(idf * freq)
        return {"indices": indices, "values": values}

    # ── Persistence ───────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "avgdl": self.avgdl,
            "doc_freq": dict(self.doc_freq),
            "n_docs": self.n_docs,
            "k1": self.k1,
            "b": self.b,
            "vocab_size": self.vocab_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BM25Encoder:
        return cls(
            avgdl=float(data["avgdl"]),
            doc_freq={str(k): int(v) for k, v in data.get("doc_freq", {}).items()},
            n_docs=int(data["n_docs"]),
            k1=float(data.get("k1", _DEFAULT_K1)),
            b=float(data.get("b", _DEFAULT_B)),
            vocab_size=int(data.get("vocab_size", _HASH_VOCAB_SIZE)),
        )
