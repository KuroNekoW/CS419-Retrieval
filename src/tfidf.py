"""Score the query with log-TF, smoothed IDF and cosine similarity."""

from collections import Counter, defaultdict
from collections.abc import Iterable
from math import log, sqrt

from .inverted_index import InvertedIndex


def score_tfidf(terms: Iterable[str], index: InvertedIndex) -> dict[str, float]:
    weights = {
        term: (1 + log(tf)) * index.vsm_idf[term]
        for term, tf in sorted(Counter(terms).items())
        if term in index.postings
    }
    query_norm = sqrt(sum(weight**2 for weight in weights.values()))
    if not query_norm:
        return {}
    numerators: dict[str, float] = defaultdict(float)
    for term, weight in weights.items():
        for doc_id, tf in index.postings[term].items():
            numerators[doc_id] += weight * (1 + log(tf)) * index.vsm_idf[term]
    return {
        doc_id: numerator / (query_norm * index.doc_norms[doc_id])
        for doc_id, numerator in numerators.items()
        if index.doc_norms[doc_id] > 0
    }
