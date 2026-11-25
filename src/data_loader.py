"""Download and validate the BEIR distribution of SciFact."""

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from shutil import copyfileobj
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile

SCIFACT_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
BEIR_ARCHIVE_MD5 = "5f7d1de60b170fc8027bb7898e2efca1"
DEFAULT_PATH = Path("data/raw/scifact")
SPLITS = ("train", "test")
FILES = ("corpus.jsonl", "queries.jsonl", "qrels/train.tsv", "qrels/test.tsv")


@dataclass(frozen=True)
class Document:
    title: str
    text: str

    @property
    def content(self) -> str:
        return f"{self.title} {self.text}"


@dataclass(frozen=True)
class Dataset:
    corpus: dict[str, Document]
    queries: dict[str, str]
    qrels: dict[str, dict[str, int]]


def _read_jsonl(path: Path, *, corpus: bool) -> dict:
    records = {}
    with path.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            location = f"{path}:{line_no}"
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{location}: invalid JSON: {error.msg}") from error
            if not isinstance(row, dict):
                raise ValueError(f"{location}: expected an object")
            record_id = row.get("_id")
            if not isinstance(record_id, str) or not record_id.strip():
                raise ValueError(f"{location}: expected a nonempty string _id")
            if record_id in records:
                raise ValueError(f"{location}: duplicate ID {record_id!r}")
            body = row.get("text")
            if not isinstance(body, str) or not body.strip():
                raise ValueError(f"{location}: expected nonempty text")
            if corpus:
                title = row.get("title")
                if not isinstance(title, str):
                    raise ValueError(f"{location}: expected a string title")
                records[record_id] = Document(title, body)
            else:
                records[record_id] = body
    if not records:
        raise ValueError(f"{path}: no records")
    return records


def _read_qrels(path: Path, queries: dict, corpus: dict) -> dict[str, dict[str, int]]:
    qrels: dict[str, dict[str, int]] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        header = next(reader, [])
        fields = ("query-id", "corpus-id", "score")
        if len(header) != len(fields) or set(header) != set(fields):
            raise ValueError(f"{path}: expected TSV header {fields}")
        qid_col, doc_col, score_col = (header.index(field) for field in fields)
        for row in reader:
            location = f"{path}:{reader.line_num}"
            if len(row) != len(fields):
                raise ValueError(f"{location}: expected three fields")
            qid, doc_id, score = row[qid_col], row[doc_col], row[score_col]
            if qid not in queries or doc_id not in corpus:
                raise ValueError(f"{location}: unknown ID in ({qid!r}, {doc_id!r})")
            if score not in {"0", "1"}:
                raise ValueError(f"{location}: invalid binary relevance score {score!r}")
            judgments = qrels.setdefault(qid, {})
            if doc_id in judgments:
                raise ValueError(f"{location}: duplicate qrel ({qid!r}, {doc_id!r})")
            judgments[doc_id] = int(score)
    if not qrels:
        raise ValueError(f"{path}: no judgments")
    return qrels


def load_splits(path: Path) -> dict[str, Dataset]:
    """Validate both splits and retain the original string IDs."""
    corpus = _read_jsonl(path / "corpus.jsonl", corpus=True)
    queries = _read_jsonl(path / "queries.jsonl", corpus=False)
    qrels = {
        split: _read_qrels(path / "qrels" / f"{split}.tsv", queries, corpus)
        for split in SPLITS
    }
    overlap = qrels["train"].keys() & qrels["test"].keys()
    if overlap:
        raise ValueError(f"train/test overlap: {len(overlap)} IDs, first {min(overlap)!r}")
    return {
        split: Dataset(corpus, {qid: queries[qid] for qid in judgments}, judgments)
        for split, judgments in qrels.items()
    }


def load_dataset(path: Path, split: str, *, validate_other_split: bool = True) -> Dataset:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; expected one of {SPLITS}")
    path = Path(path)
    if validate_other_split:
        return load_splits(path)[split]
    corpus = _read_jsonl(path / "corpus.jsonl", corpus=True)
    queries = _read_jsonl(path / "queries.jsonl", corpus=False)
    judgments = _read_qrels(path / "qrels" / f"{split}.tsv", queries, corpus)
    return Dataset(corpus, {qid: queries[qid] for qid in judgments}, judgments)


def _digest(path: Path, algorithm: str = "sha256") -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def download_scifact(path: Path = DEFAULT_PATH, *, archive: Path | None = None) -> Path:
    """Stage and validate the official ZIP before publishing the dataset directory."""
    if path.exists():
        load_splits(path)
        return path

    origin = "download" if archive is None else "local"
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as staging_dir:
        staging = Path(staging_dir)
        if archive is None:
            archive = staging / "scifact.zip"
            with urlopen(SCIFACT_URL, timeout=30) as source, archive.open("wb") as target:
                copyfileobj(source, target)

        beir_match = _digest(archive, "md5") == BEIR_ARCHIVE_MD5
        if origin == "download" and not beir_match:
            raise ValueError("downloaded archive does not match the checksum published by BEIR")

        dataset = staging / "scifact"
        with ZipFile(archive) as source:
            for name in FILES:
                target = dataset / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(f"scifact/{name}") as entry, target.open("xb") as output:
                    copyfileobj(entry, output)
        load_splits(dataset)
        digest = _digest(archive)
        manifest = {
            "dataset": "BEIR SciFact",
            "version": f"sha256:{digest}",
            "source_url": SCIFACT_URL,
            "archive_sha256": digest,
            "archive_origin": origin,
            "matches_beir_archive_checksum": beir_match,
            "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
            "splits": list(SPLITS),
            "file_sha256": {name: _digest(dataset / name) for name in FILES},
            "license_sources": {
                "BEIR dataset card": {
                    "license": "CC-BY-SA-4.0",
                    "url": "https://huggingface.co/datasets/BeIR/scifact",
                },
                "Original SciFact": {
                    "license": "CC-BY-NC-2.0",
                    "url": "https://github.com/allenai/scifact/blob/master/LICENSE.md",
                },
            },
        }
        (dataset / "dataset_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        # Keep existing data if a concurrent invocation has already published it.
        try:
            dataset.rename(path)
        except OSError:
            if not path.is_dir():
                raise
            load_splits(path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--archive", type=Path, help="Use a local copy of the official ZIP")
    args = parser.parse_args()
    try:
        print(download_scifact(args.path, archive=args.archive))
    except (OSError, ValueError, KeyError, BadZipFile) as error:
        parser.exit(1, f"SciFact: {error}\n")


if __name__ == "__main__":
    main()
