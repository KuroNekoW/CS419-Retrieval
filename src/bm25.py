"""Score distinct query terms using Okapi BM25."""

import warnings
from collections import defaultdict
from collections.abc import Iterable
from math import isfinite

from .inverted_index import InvertedIndex


def score_bm25(
    terms: Iterable[str], index: InvertedIndex, *, k1: float = 1.2, b: float = 0.75
) -> dict[str, float]:
    if not isfinite(k1) or k1 < 0 or not 0 <= b <= 1:
        raise ValueError("BM25 requires finite k1 >= 0 and 0 <= b <= 1")
    if index.avgdl == 0:
        warnings.warn("BM25 index average document length is zero", RuntimeWarning, stacklevel=2)
        return {}
    scores: dict[str, float] = defaultdict(float)
    for term in sorted(set(terms)):
        for doc_id, tf in index.postings.get(term, {}).items():
            length_ratio = index.doc_lengths[doc_id] / index.avgdl
            denominator = tf + k1 * (1 - b + b * length_ratio)
            scores[doc_id] += index.bm25_idf[term] * tf * (k1 + 1) / denominator
    return dict(scores)
