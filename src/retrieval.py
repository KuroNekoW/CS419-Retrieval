"""Analyze queries and return compact, deterministic rankings."""

from dataclasses import dataclass
from math import isfinite

from .bm25 import score_bm25
from .inverted_index import InvertedIndex
from .preprocessing import analyze
from .tfidf import score_tfidf


@dataclass(frozen=True)
class Hit:
    doc_id: str
    rank: int
    score: float


def search(
    query: str,
    model: str,
    index: InvertedIndex,
    top_k: int | None = None,
    *,
    k1: float = 1.2,
    b: float = 0.75,
) -> list[Hit]:
    if top_k is not None and top_k < 0:
        raise ValueError("top_k must be nonnegative")
    terms = analyze(query, index.config)
    if model == "vsm":
        scores = score_tfidf(terms, index)
    elif model == "bm25":
        scores = score_bm25(terms, index, k1=k1, b=b)
    else:
        raise ValueError(f"unknown model {model!r}")
    positive = ((doc_id, score) for doc_id, score in scores.items() if score > 0 and isfinite(score))
    ranked = sorted(positive, key=lambda item: (-item[1], item[0]))
    return [Hit(doc_id, rank, score) for rank, (doc_id, score) in enumerate(ranked[:top_k], 1)]
