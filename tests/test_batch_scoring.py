import pytest

from src.batch_scoring import BatchScorer
from src.data_loader import Document
from src.experiments import DevCandidate
from src.inverted_index import build_index
from src.preprocessing import AnalyzerConfig
from src.retrieval import search


@pytest.mark.parametrize("kind", ["word", "char"])
def test_batch_and_interactive_rankings_match_exactly(kind):
    config = AnalyzerConfig(kind)
    corpus = {
        "2": Document("", "alpha alpha cancer"),
        "10": Document("", "alpha alpha cancer"),
        "3": Document("alpha", "red roses"),
        "0": Document("", ""),
    }
    index, _ = build_index(corpus, config, corpus_sha256="toy")
    batch = BatchScorer(index)
    for model, k1, b in (("vsm", None, None), ("bm25", 1.2, 0.75), ("bm25", 1.5, 0.5)):
        candidate = DevCandidate("toy", model, config, k1, b)
        kwargs = {"k1": k1, "b": b} if model == "bm25" else {}
        for query in ("alpha alpha", "cancre", "red roses", "", "zzz"):
            expected = search(query, model, index, **kwargs)
            ids, scores = batch.rank(query, candidate)
            assert ids.tolist() == [hit.doc_id for hit in expected]
            assert scores.tolist() == [hit.score for hit in expected]
