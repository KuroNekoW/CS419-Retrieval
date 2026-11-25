import unittest
from math import log, sqrt
from pathlib import Path
from tempfile import TemporaryDirectory

from src.data_loader import Document
from src.inverted_index import build_index, load_index, save_index
from src.preprocessing import AnalyzerConfig
from src.retrieval import search


class RetrievalTest(unittest.TestCase):
    def setUp(self):
        self.corpus = {
            "2": Document("alpha", "alpha beta"),
            "1": Document("", "alpha"),
            "0": Document("", ""),
        }
        self.index, _ = build_index(self.corpus, AnalyzerConfig(), corpus_sha256="toy")

    def test_index_statistics_and_roundtrip(self):
        self.assertEqual(self.index.df, {"alpha": 2, "beta": 1})
        self.assertEqual(self.index.cf, {"alpha": 3, "beta": 1})
        self.assertEqual(self.index.postings, {"alpha": {"2": 2, "1": 1}, "beta": {"2": 1}})
        self.assertEqual(self.index.doc_lengths, {"2": 3, "1": 1, "0": 0})
        self.assertEqual(self.index.avgdl, 4 / 3)
        self.assertEqual(self.index.doc_norms["0"], 0)
        with TemporaryDirectory() as parent:
            path = Path(parent) / "index.json"
            save_index(self.index, path)
            self.assertEqual(load_index(path), self.index)
            self.assertEqual(search("alpha", "vsm", load_index(path)), search("alpha", "vsm", self.index))

    def test_vsm_uses_full_document_norm(self):
        alpha = (1 + log(2)) * (1 + log(4 / 3))
        beta = 1 + log(4 / 2)
        hits = search("alpha oov", "vsm", self.index)
        self.assertEqual([(hit.doc_id, hit.rank) for hit in hits], [("1", 1), ("2", 2)])
        self.assertAlmostEqual(hits[0].score, 1)
        self.assertAlmostEqual(hits[1].score, alpha / sqrt(alpha**2 + beta**2))
        self.assertEqual(search("oov", "vsm", self.index), [])

    def test_bm25_formula_and_parameter_overrides(self):
        hits = search("alpha alpha", "bm25", self.index, k1=1.5, b=0.5)
        self.assertEqual(hits, search("alpha", "bm25", self.index, k1=1.5, b=0.5))
        self.assertEqual([hit.doc_id for hit in hits], ["2", "1"])
        for hit, tf, length in zip(hits, (2, 1), (3, 1), strict=True):
            idf = log(1 + 1.5 / 2.5)
            self.assertAlmostEqual(hit.score, idf * tf * 2.5 / (tf + 1.5 * (0.5 + 0.5 * length / (4 / 3))))
        self.assertEqual(search("", "bm25", self.index), [])
        with self.assertRaises(ValueError):
            search("alpha", "bm25", self.index, b=1.1)

    def test_ties_and_index_with_no_retained_terms(self):
        index, _ = build_index(
            {"2": Document("", "alpha"), "10": Document("", "alpha")},
            AnalyzerConfig(),
            corpus_sha256="toy",
        )
        for model in ("vsm", "bm25"):
            self.assertEqual([hit.doc_id for hit in search("alpha", model, index)], ["10", "2"])
            self.assertEqual([hit.doc_id for hit in search("alpha", model, index, 1)], ["10"])
            self.assertEqual(search("alpha", model, index, 0), [])
        empty, _ = build_index(self.corpus, AnalyzerConfig(min_df=4), corpus_sha256="toy")
        self.assertEqual(search("alpha", "vsm", empty), [])
        with self.assertWarns(RuntimeWarning):
            self.assertEqual(search("alpha", "bm25", empty), [])
