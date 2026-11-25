"""Use sparse posting arrays for repeated queries against a fixed index."""

from collections import Counter
from math import log, sqrt

import numpy as np

from .experiments import DevCandidate
from .inverted_index import InvertedIndex
from .preprocessing import analyze


class BatchScorer:
    """Keep one accumulator per document and never build a dense term matrix."""

    def __init__(self, index: InvertedIndex):
        self.index = index
        self.doc_ids = np.array(sorted(index.doc_lengths), dtype=object)
        ordinal = {doc_id: pos for pos, doc_id in enumerate(self.doc_ids)}
        self.docs = {
            term: np.fromiter((ordinal[doc_id] for doc_id in hits), dtype=np.intp, count=len(hits))
            for term, hits in index.postings.items()
        }
        self.tf = {
            term: np.fromiter(hits.values(), dtype=np.float64, count=len(hits))
            for term, hits in index.postings.items()
        }
        self.norms = np.array([index.doc_norms[doc_id] for doc_id in self.doc_ids])
        self.length_ratios = (
            np.array([index.doc_lengths[doc_id] for doc_id in self.doc_ids]) / index.avgdl
            if index.avgdl else np.zeros(index.n_docs)
        )
        max_tf = max((max(hits.values()) for hits in index.postings.values()), default=0)
        log_tf = np.array([0.0, *(1 + log(tf) for tf in range(1, max_tf + 1))])
        self.log_tf = {term: log_tf[values.astype(np.intp)] for term, values in self.tf.items()}
        self.bm25_parameters: tuple[float, float] | None = None
        self.bm25_cache: dict[str, np.ndarray] = {}

    def rank(self, query: str, candidate: DevCandidate) -> tuple[np.ndarray, np.ndarray]:
        counts = Counter(analyze(query, self.index.config))
        terms = sorted(counts.keys() & self.docs.keys())
        scores = np.zeros(self.index.n_docs)
        if candidate.scorer == "vsm":
            idf = self.index.vsm_idf
            weights = {term: (1 + log(counts[term])) * idf[term] for term in terms}
            norm = sqrt(sum(weight**2 for weight in weights.values()))
            if norm:
                for term, weight in weights.items():
                    scores[self.docs[term]] += weight * self.log_tf[term] * idf[term]
                matched = np.flatnonzero(scores)
                scores[matched] /= norm * self.norms[matched]
        elif terms:
            k1, b = candidate.k1, candidate.b
            if (k1, b) != self.bm25_parameters:
                self.bm25_parameters = (k1, b)
                self.bm25_cache.clear()
            for term in terms:
                docs = self.docs[term]
                contributions = self.bm25_cache.get(term)
                if contributions is None:
                    tf = self.tf[term]
                    contributions = self.index.bm25_idf[term] * tf * (k1 + 1) / (
                        tf + k1 * (1 - b + b * self.length_ratios[docs])
                    )
                    self.bm25_cache[term] = contributions
                scores[docs] += contributions

        positive = np.flatnonzero((scores > 0) & np.isfinite(scores))
        ranked = positive[np.argsort(-scores[positive], kind="stable")]
        return self.doc_ids[ranked], scores[ranked]
