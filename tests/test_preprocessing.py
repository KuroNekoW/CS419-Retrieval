import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.preprocessing import AnalyzerConfig, analyze
from src.term_selection import TermStats, fit_vocabulary, write_vocabulary


class PreprocessingTest(unittest.TestCase):
    def test_normalization_and_character_boundaries(self):
        self.assertEqual(analyze("ＮＯ, can-ＣER １２!", AnalyzerConfig()), ["no", "can", "cer", "12"])
        self.assertEqual(
            analyze("ＡＢ aaaaa z", AnalyzerConfig("char")),
            ["short:ab", "aaa", "aaa", "aaa", "aaaa", "aaaa", "aaaaa", "short:z"],
        )
        self.assertEqual(analyze("... ", AnalyzerConfig("char")), [])

    def test_document_vs_collection_frequency_and_export(self):
        config = AnalyzerConfig(min_df=2, max_df_ratio=2 / 3)
        vocabulary, stats = fit_vocabulary(["a a b c", "a b", "a"], config)
        self.assertEqual(vocabulary, {"b"})
        self.assertEqual(
            stats,
            {
                "a": TermStats(3, 4, False, "above_max_df_ratio"),
                "b": TermStats(2, 2, True, "selected"),
                "c": TermStats(1, 1, False, "below_min_df"),
            },
        )
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            write_vocabulary(output, config, stats)
            with (output / "vocabulary_word_selected.tsv").open(newline="", encoding="utf-8") as stream:
                self.assertEqual([row["term"] for row in csv.DictReader(stream, delimiter="\t")], ["b"])
            summary = json.loads((output / "vocabulary_word_stats.json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(summary["distinct_retained_percent"], 100 / 3)
            self.assertAlmostEqual(summary["occurrences_retained_percent"], 200 / 7)

            write_vocabulary(output, config, fit_vocabulary([], config)[1])
            summary = json.loads((output / "vocabulary_word_stats.json").read_text(encoding="utf-8"))
            self.assertIsNone(summary["distinct_retained_percent"])
            self.assertIsNone(summary["occurrences_retained_percent"])

    def test_character_frequency(self):
        vocabulary, stats = fit_vocabulary(["aaaaa", "aaa"], AnalyzerConfig("char", min_df=2))
        self.assertEqual(vocabulary, {"aaa"})
        self.assertEqual(stats["aaa"], TermStats(2, 4, True, "selected"))
