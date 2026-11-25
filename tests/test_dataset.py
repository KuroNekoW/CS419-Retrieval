import csv
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from src.data_loader import download_scifact, load_dataset
from src.dataset_stats import write_stats

HEADER = "query-id\tcorpus-id\tscore\n"


class DatasetTest(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "raw" / "scifact"
        self.archive = self.root / "scifact.zip"
        self.files = {
            "corpus.jsonl": (
                '{"_id":"01","title":"Ａ-1","text":"heart health"}\n'
                '{"_id":"02","title":"","text":"A study"}\n'
            ),
            "queries.jsonl": '{"_id":"003","text":"Heart?"}\n{"_id":"04","text":"A study"}\n',
            "qrels/train.tsv": HEADER + "003\t01\t1\n003\t02\t0\n",
            "qrels/test.tsv": HEADER + "04\t02\t1\n",
        }

    def make_archive(self):
        with ZipFile(self.archive, "w") as archive:
            for name, content in self.files.items():
                archive.writestr(f"scifact/{name}", content)

    def test_local_zip_manifest_stats_and_retry(self):
        self.make_archive()
        self.assertEqual(download_scifact(self.path, archive=self.archive), self.path)
        dataset = load_dataset(self.path, "train")
        self.assertEqual(dataset.qrels, {"003": {"01": 1, "02": 0}})
        self.assertEqual(set(dataset.corpus), {"01", "02"})
        self.assertEqual(list(dataset.queries), ["003"])
        self.assertEqual(dataset.corpus["01"].content, "Ａ-1 heart health")
        manifest_path = self.path / "dataset_manifest.json"
        original = manifest_path.read_bytes()
        manifest = json.loads(original)
        self.assertEqual(manifest["archive_sha256"], hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.assertEqual(manifest["archive_origin"], "local")
        download_scifact(self.path)
        self.assertEqual(original, manifest_path.read_bytes())

        output = self.root / "processed"
        write_stats(self.path, output)
        stats = json.loads((output / "dataset_stats.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["documents"]["length"]["mean"], 3)
        self.assertEqual(stats["splits"]["train"]["positive_qrels"], 1)
        self.assertEqual(stats["splits"]["train"]["score_counts"], {"0": 1, "1": 1})
        with (output / "dataset_stats.csv").open(encoding="utf-8", newline="") as stream:
            rows = {row["metric"]: row["value"] for row in csv.DictReader(stream)}
        self.assertEqual(rows["splits.test.queries"], "1")

    def test_invalid_archive_does_not_publish_partial_data(self):
        cases = (
            ("qrels/test.tsv", HEADER + "04\t99\t1\n", "unknown ID"),
            ("qrels/test.tsv", HEADER + "003\t02\t1\n", "overlap"),
            ("qrels/test.tsv", HEADER + "04\t02\t2\n", "invalid binary"),
            ("qrels/test.tsv", HEADER + "04\t02\t1\n04\t02\t1\n", "duplicate qrel"),
            ("queries.jsonl", '{"_id":"03","text":" "}\n', "nonempty text"),
            ("queries.jsonl", '{"_id":"03","text":"A"}\n{"_id":"03","text":"B"}\n', "duplicate ID"),
        )
        for name, content, message in cases:
            with self.subTest(message=message):
                original = self.files[name]
                self.files[name] = content
                self.make_archive()
                self.files[name] = original
                with self.assertRaisesRegex(ValueError, message):
                    download_scifact(self.path, archive=self.archive)
                self.assertFalse(self.path.exists())
