"""Write JSON and CSV statistics for the validated SciFact splits."""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median

from .data_loader import DEFAULT_PATH, SCIFACT_URL, load_splits
from .preprocessing import tokenize


def _distribution(values: list[int]) -> dict[str, int | float]:
    return {
        "min": min(values),
        "median": median(values),
        "mean": mean(values),
        "max": max(values),
    }


def dataset_stats(path: Path) -> dict:
    splits = load_splits(path)
    corpus = splits["train"].corpus
    lengths = [len(tokenize(doc.content)) for doc in corpus.values()]
    example_doc_id = min(corpus)
    example_doc = corpus[example_doc_id]
    manifest = path / "dataset_manifest.json"
    source_url = (
        json.loads(manifest.read_text(encoding="utf-8"))["source_url"]
        if manifest.is_file()
        else SCIFACT_URL
    )
    report = {
        "dataset": "BEIR SciFact",
        "language": "en",
        "domain": "scientific claims and article abstracts",
        "source_url": source_url,
        "length_unit": "ASCII alphanumeric tokens after NFKC and lowercase, before term filtering",
        "documents": {
            "count": len(corpus),
            "length": _distribution(lengths),
            "empty_titles": sum(not doc.title.strip() for doc in corpus.values()),
            "invalid_records": 0,
            "empty_texts": 0,
            "zero_token_documents": lengths.count(0),
            "example": {"id": example_doc_id, "title": example_doc.title},
        },
        "splits": {},
    }
    for split, dataset in splits.items():
        scores = Counter(
            score for judgments in dataset.qrels.values() for score in judgments.values()
        )
        relevant = [sum(score > 0 for score in judgments.values()) for judgments in dataset.qrels.values()]
        query_lengths = [len(tokenize(query)) for query in dataset.queries.values()]
        example_qid = min(dataset.queries)
        report["splits"][split] = {
            "queries": len(dataset.queries),
            "qrels": scores.total(),
            "positive_qrels": sum(relevant),
            "score_counts": dict(sorted(scores.items())),
            "relevant_per_query": _distribution(relevant),
            "relevant_per_query_counts": dict(sorted(Counter(relevant).items())),
            "query_length": _distribution(query_lengths),
            "invalid_records": 0,
            "empty_texts": 0,
            "zero_token_queries": query_lengths.count(0),
            "example": {"id": example_qid, "text": dataset.queries[example_qid]},
        }
    return report


def _metrics(report: dict, prefix: str = ""):
    for name, value in report.items():
        if name == "example":
            continue
        key = f"{prefix}.{name}" if prefix else str(name)
        if isinstance(value, dict):
            yield from _metrics(value, key)
        else:
            yield key, value


def write_stats(path: Path, output: Path) -> None:
    stats = dataset_stats(path)
    output.mkdir(parents=True, exist_ok=True)
    (output / "dataset_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output / "dataset_stats.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("metric", "value"))
        writer.writerows(_metrics(stats))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--output", type=Path, default=Path("data/processed/scifact"))
    args = parser.parse_args()
    try:
        write_stats(args.path, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"SciFact: {error}\n")


if __name__ == "__main__":
    main()
