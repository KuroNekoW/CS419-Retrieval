"""Build indexes, run interactive queries and export rankings."""

import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from .data_loader import DEFAULT_PATH, SPLITS, load_dataset
from .experiment_runner import run_experiments, tune
from .experiments import DEFAULT_CONFIG, experiment_counts, load_protocol, write_experiment_plan
from .inverted_index import build_index, load_index, save_index
from .noise_generator import NOISE_TYPES, NoiseCondition, write_noise_run
from .preprocessing import AnalyzerConfig, tokenize
from .retrieval import search
from .term_selection import write_vocabulary


def _index_directory(args: argparse.Namespace) -> Path:
    return args.indexes / args.analyzer


def _build(args: argparse.Namespace) -> None:
    directory = _index_directory(args)
    if directory.exists():
        raise FileExistsError(f"{directory} already exists; choose a new --indexes directory")
    corpus = load_dataset(args.data, "train").corpus
    with (args.data / "corpus.jsonl").open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    config = AnalyzerConfig(args.analyzer, args.min_df, args.max_df_ratio)
    start = perf_counter()
    index, vocabulary = build_index(corpus, config, corpus_sha256=checksum)
    build_seconds = perf_counter() - start
    directory.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=directory.parent) as staging:
        staged = Path(staging) / directory.name
        index_path = staged / "index.json"
        save_index(index, index_path)
        write_vocabulary(staged, config, vocabulary)
        with (staged / "index_stats.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("analyzer", "documents", "vocabulary", "postings", "avgdl", "bytes", "build_seconds"))
            writer.writerow((
                config.kind, index.n_docs, len(index.postings), sum(index.df.values()),
                index.avgdl, index_path.stat().st_size, build_seconds,
            ))
        staged.rename(directory)
    print(directory / "index.json")


def _search(args: argparse.Namespace) -> None:
    index = load_index(_index_directory(args) / "index.json")
    hits = search(args.query, args.model, index, args.top_k, k1=args.k1, b=args.b)
    ranking = [asdict(hit) for hit in hits]
    if args.output:
        result = {
            "query": args.query,
            "model": args.model,
            "analyzer": asdict(index.config),
            "corpus_sha256": index.corpus_sha256,
            "top_k": args.top_k,
            "ranking": ranking,
        }
        if args.model == "bm25":
            result["parameters"] = {"k1": args.k1, "b": args.b}
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream)
            stream.write("\n")
    for row in ranking:
        row["title"] = index.titles[row["doc_id"]]
        row["snippet"] = index.snippets[row["doc_id"]]
    print(json.dumps(ranking, ensure_ascii=True))


def _generate_noise(args: argparse.Namespace) -> None:
    condition = NoiseCondition(args.noise_type, args.seed, args.rate, args.fixed_k)
    dataset = load_dataset(args.data, args.split)
    output = args.output or Path("data/processed/noise") / args.split / condition.label
    vocabulary: set[str] = set()
    for doc in dataset.corpus.values():
        vocabulary.update(tokenize(doc.content))
    write_noise_run(output, dataset.queries, args.split, condition, vocabulary=vocabulary)
    print(output / "noisy_queries.jsonl")


def _plan_experiments(args: argparse.Namespace) -> None:
    protocol = load_protocol(args.config)
    if args.output:
        write_experiment_plan(protocol, args.output)
    print(json.dumps(experiment_counts(protocol)))


def _tune(args: argparse.Namespace) -> None:
    tune(load_protocol(args.config), args.data, args.output)
    print(args.output / "selected_config.yaml")


def _experiment(args: argparse.Namespace) -> None:
    run_experiments(
        load_protocol(args.config), args.data, args.selected_config, args.output, set(args.groups)
    )
    print(args.output / "metrics" / "summary.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-index")
    query = commands.add_parser("search")
    noise = commands.add_parser("generate-noise")
    plan = commands.add_parser("plan-experiments")
    tuning = commands.add_parser("tune")
    experiment = commands.add_parser("experiment")
    for command in (build, query):
        command.add_argument("--indexes", type=Path, default=Path("indexes"))
        command.add_argument("--analyzer", choices=("word", "char"), default="word")
    build.add_argument("--data", type=Path, default=DEFAULT_PATH)
    build.add_argument("--min-df", type=int, default=1)
    build.add_argument("--max-df-ratio", type=float, default=1.0)
    build.set_defaults(handler=_build)
    query.add_argument("--model", choices=("vsm", "bm25"), required=True)
    query.add_argument("--query", required=True)
    query.add_argument("--top-k", type=int, default=10)
    query.add_argument("--k1", type=float, default=1.2)
    query.add_argument("--b", type=float, default=0.75)
    query.add_argument("--output", type=Path)
    query.set_defaults(handler=_search)
    noise.add_argument("--data", type=Path, default=DEFAULT_PATH)
    noise.add_argument("--split", choices=SPLITS, required=True)
    noise.add_argument("--noise-type", choices=NOISE_TYPES, default="mixed")
    noise.add_argument("--seed", type=int, default=42)
    noise.add_argument("--output", type=Path)
    amount = noise.add_mutually_exclusive_group(required=True)
    amount.add_argument("--rate", type=float)
    amount.add_argument("--fixed-k", type=int, choices=(1, 2))
    noise.set_defaults(handler=_generate_noise)
    plan.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    plan.add_argument("--output", type=Path)
    plan.set_defaults(handler=_plan_experiments)
    for command in (tuning, experiment):
        command.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
        command.add_argument("--data", type=Path, default=DEFAULT_PATH)
        command.add_argument("--output", type=Path, required=True)
    tuning.add_argument("--split", choices=("train",), default="train")
    tuning.set_defaults(handler=_tune)
    experiment.add_argument("--split", choices=("test",), default="test")
    experiment.add_argument("--selected-config", type=Path, required=True)
    experiment.add_argument(
        "--groups", nargs="+", choices=("E1", "E2", "E3", "E4"), default=("E1", "E2", "E3", "E4")
    )
    experiment.set_defaults(handler=_experiment)
    args = parser.parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
