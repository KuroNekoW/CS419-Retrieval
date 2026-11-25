"""Fit and export the corpus-only term vocabulary."""

import argparse
import csv
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from .data_loader import DEFAULT_PATH, load_dataset
from .preprocessing import AnalyzerConfig, analyze


@dataclass(frozen=True)
class TermStats:
    df: int
    cf: int
    selected: bool
    reason: str


def fit_vocabulary(
    corpus: Iterable[str], config: AnalyzerConfig
) -> tuple[set[str], dict[str, TermStats]]:
    df: Counter[str] = Counter()
    cf: Counter[str] = Counter()
    document_count = 0
    for document in corpus:
        counts = Counter(analyze(document, config))
        df.update(counts.keys())
        cf.update(counts)
        document_count += 1

    stats = {}
    for term, frequency in df.items():
        reason = "selected"
        if frequency < config.min_df:
            reason = "below_min_df"
        elif frequency / document_count > config.max_df_ratio:
            reason = "above_max_df_ratio"
        stats[term] = TermStats(frequency, cf[term], reason == "selected", reason)
    return {term for term, info in stats.items() if info.selected}, stats


def write_vocabulary(
    output: Path, config: AnalyzerConfig, stats: dict[str, TermStats]
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    stem = f"vocabulary_{config.kind}"
    fields = ("term", "df", "cf", "selected", "reason")
    with (
        (output / f"{stem}.tsv").open("w", encoding="utf-8", newline="") as all_terms,
        (output / f"{stem}_selected.tsv").open("w", encoding="utf-8", newline="") as retained_terms,
    ):
        candidates = csv.writer(all_terms, delimiter="\t")
        retained = csv.writer(retained_terms, delimiter="\t")
        candidates.writerow(fields)
        retained.writerow(fields)
        for term, info in sorted(stats.items()):
            row = (term, info.df, info.cf, int(info.selected), info.reason)
            candidates.writerow(row)
            if info.selected:
                retained.writerow(row)

    distinct = len(stats)
    selected = sum(info.selected for info in stats.values())
    occurrences = sum(info.cf for info in stats.values())
    kept_occurrences = sum(info.cf for info in stats.values() if info.selected)
    summary = {
        "analyzer": asdict(config),
        "distinct_candidates": distinct,
        "distinct_selected": selected,
        "distinct_retained_percent": 100 * selected / distinct if distinct else None,
        "total_occurrences": occurrences,
        "retained_occurrences": kept_occurrences,
        "occurrences_retained_percent": 100 * kept_occurrences / occurrences if occurrences else None,
    }
    (output / f"{stem}_stats.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--output", type=Path, default=Path("results/vocabularies"))
    parser.add_argument("--analyzer", choices=("word", "char"), default="word")
    parser.add_argument("--min-df", type=int, default=1)
    parser.add_argument("--max-df-ratio", type=float, default=1.0)
    args = parser.parse_args()
    try:
        config = AnalyzerConfig(args.analyzer, args.min_df, args.max_df_ratio)
        corpus = load_dataset(args.path, "train").corpus
        _, stats = fit_vocabulary((doc.content for doc in corpus.values()), config)
        write_vocabulary(args.output, config, stats)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Vocabulary: {error}\n")


if __name__ == "__main__":
    main()
