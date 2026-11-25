"""Run dev tuning and test experiments with auditable artifacts."""

import csv
import hashlib
import json
import platform
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from itertools import groupby
from math import ceil
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter, perf_counter_ns

import yaml

from .batch_scoring import BatchScorer
from .data_loader import FILES, Document, load_dataset
from .evaluation import evaluate
from .experiments import DevCandidate, ExperimentProtocol
from .inverted_index import InvertedIndex, build_index, load_index, save_index
from .noise_generator import write_noise_run
from .preprocessing import AnalyzerConfig, analyze, tokenize
from .term_selection import write_vocabulary


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _json_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def _code_digest() -> str:
    return _json_digest({path.name: _sha256(path) for path in sorted(Path(__file__).parent.glob("*.py"))})


def _csv(path: Path, rows: Iterable[dict]) -> None:
    rows = iter(rows)
    first = next(rows, None)
    with path.open("w", encoding="utf-8", newline="") as stream:
        if first is not None:
            writer = csv.DictWriter(stream, fieldnames=list(first))
            writer.writeheader()
            writer.writerow(first)
            writer.writerows(rows)


def _index_key(config: AnalyzerConfig) -> str:
    return f"{config.kind}-{_json_digest(asdict(config))[:16]}"


def _build_dev_index(
    output: Path, corpus: dict[str, Document], config: AnalyzerConfig, corpus_sha256: str
) -> tuple[InvertedIndex, str]:
    directory = output / "indexes" / _index_key(config)
    start = perf_counter()
    index, terms = build_index(corpus, config, corpus_sha256=corpus_sha256)
    elapsed = perf_counter() - start
    index_path = directory / "index.json"
    save_index(index, index_path)
    write_vocabulary(directory, config, terms)
    _csv(directory / "index_stats.csv", [{
        "analyzer": config.kind, "documents": index.n_docs, "vocabulary": len(index.postings),
        "postings": sum(index.df.values()), "avgdl": index.avgdl,
        "bytes": index_path.stat().st_size, "build_seconds": elapsed,
    }])
    return index, _sha256(index_path)


def tune(protocol: ExperimentProtocol, data: Path, output: Path) -> None:
    """Score E0 candidates on train and publish the chosen configurations."""
    if output.exists():
        raise FileExistsError(f"{output} already exists")
    dataset = load_dataset(data, "train", validate_other_split=False)
    hashes = {name: _sha256(data / name) for name in FILES if name != "qrels/test.tsv"}
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as staging:
        work = Path(staging) / "tune"
        by_index: dict[AnalyzerConfig, list[DevCandidate]] = {}
        for candidate in protocol.dev_candidates:
            by_index.setdefault(candidate.analyzer, []).append(candidate)
        scores = {}
        index_hashes = {}
        for config, candidates in by_index.items():
            index, index_hashes[_index_key(config)] = _build_dev_index(
                work, dataset.corpus, config, hashes["corpus.jsonl"]
            )
            scorer = BatchScorer(index)
            for candidate in candidates:
                rankings = {
                    qid: scorer.rank(query, candidate)[0].tolist()
                    for qid, query in dataset.queries.items()
                }
                result = evaluate(rankings, dataset.qrels)
                if result.mean_ap is None:
                    raise ValueError("E0 needs at least one query with a positive judgment")
                scores[candidate.candidate_id] = result.mean_ap
            del scorer, index
        winners = protocol.select_dev_winners(scores)
        _csv(work / "tuning.csv", (
            {
                "candidate_id": candidate.candidate_id, "model_id": candidate.model_id,
                "scorer": candidate.scorer, **asdict(candidate.analyzer),
                "k1": candidate.k1, "b": candidate.b, "MAP": scores[candidate.candidate_id],
                "n_queries": result.n_queries, "selected": candidate == winners[candidate.model_id],
            }
            for candidate in protocol.dev_candidates
        ))
        selected = {
            "split": "train",
            "metric": "MAP",
            "candidate_count": len(scores),
            "protocol_sha256": _json_digest(protocol.as_plan()),
            "source_code_sha256": _code_digest(),
            "dev_data_sha256": hashes,
            "tuning_sha256": _sha256(work / "tuning.csv"),
            "models": {
                model: {"candidate_id": candidate.candidate_id, **asdict(candidate)}
                for model, candidate in winners.items()
            },
            "index_sha256": index_hashes,
        }
        (work / "selected_config.yaml").write_text(yaml.safe_dump(selected), encoding="utf-8")
        work.rename(output)


def _load_selection(
    protocol: ExperimentProtocol, selected_path: Path, hashes: dict[str, str]
) -> tuple[dict[str, DevCandidate], dict[str, str], str]:
    try:
        selected = yaml.safe_load(selected_path.read_bytes())
        if (
            selected["split"] != "train"
            or selected["metric"] != "MAP"
            or selected["protocol_sha256"] != _json_digest(protocol.as_plan())
            or selected["source_code_sha256"] != _code_digest()
            or selected["dev_data_sha256"] != {name: hashes[name] for name in FILES if name != "qrels/test.tsv"}
        ):
            raise ValueError("E0 selection does not match current protocol, code or training data")
        tuning = selected_path.with_name("tuning.csv")
        if selected["tuning_sha256"] != _sha256(tuning):
            raise ValueError("E0 tuning.csv checksum mismatch")
        with tuning.open(encoding="utf-8", newline="") as stream:
            scores = {row["candidate_id"]: float(row["MAP"]) for row in csv.DictReader(stream)}
        winners = protocol.select_dev_winners(scores)
        if selected["models"] != {
            model: {"candidate_id": candidate.candidate_id, **asdict(candidate)}
            for model, candidate in winners.items()
        }:
            raise ValueError("selected models do not match the E0 winners")
        return winners, selected["index_sha256"], selected["source_code_sha256"]
    except (KeyError, TypeError, yaml.YAMLError) as error:
        raise ValueError(f"invalid E0 selection {selected_path}: {error}") from error


def _rank_queries(
    path: Path,
    queries: Mapping[str, str],
    variants: Mapping[str, dict] | None,
    candidate: DevCandidate,
    scorer: BatchScorer,
) -> tuple[dict[str, list[str]], dict[str, float], dict[str, int]]:
    rankings = {}
    latency = {}
    oov = {}
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for qid, original in queries.items():
            variant = variants[qid] if variants is not None else None
            query = variant["noisy"] if variant else original
            start = perf_counter_ns()
            doc_ids, scores = scorer.rank(query, candidate)
            latency[qid] = (perf_counter_ns() - start) / 1_000_000
            rankings[qid] = ids = doc_ids.tolist()
            oov[qid] = sum(
                term not in scorer.index.postings for term in analyze(query, scorer.index.config)
            )
            stream.write(json.dumps({
                "qid": qid, "variant_id": variant["variant_id"] if variant else f"test/clean/{qid}",
                "ranking": [
                    {"doc_id": doc_id, "rank": rank, "score": score}
                    for rank, (doc_id, score) in enumerate(zip(ids, scores.tolist(), strict=True), 1)
                ],
            }, separators=(",", ":")) + "\n")
    return rankings, latency, oov


def run_experiments(
    protocol: ExperimentProtocol,
    data: Path,
    selected_path: Path,
    output: Path,
    groups: set[str],
) -> None:
    """Use a frozen E0 selection to run requested test groups and their clean baselines."""
    if output.exists():
        raise FileExistsError(f"{output} already exists")
    if not groups or not groups <= {"E1", "E2", "E3", "E4"}:
        raise ValueError("select at least one test group from E1 through E4")
    hashes = {name: _sha256(data / name) for name in FILES}
    candidates, index_hashes, code_hash = _load_selection(protocol, selected_path, hashes)
    selection_hash = _sha256(selected_path)
    dataset = load_dataset(data, "test")
    sets = {
        "test": sorted(dataset.queries),
        "e4_eligible": protocol.e4_query_ids(dataset.queries),
    }
    vocabulary = {term for doc in dataset.corpus.values() for term in tokenize(doc.content)}
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as staging:
        work = Path(staging) / "experiment"
        for name in ("runs", "metrics", "manifests"):
            (work / name).mkdir(parents=True)
        per_query = []
        summaries = []
        baseline_maps = {}
        indexes = {}
        runs = (run for run in protocol.test_runs if run.experiment_id in (groups | {"E1"}))
        for noise_key, shared_runs in groupby(runs, key=lambda run: run.noise_key):
            variants = None
            noise_sha256 = None
            for run in shared_runs:
                qids = sets[run.query_set]
                queries = {qid: dataset.queries[qid] for qid in qids}
                qrels = {qid: dataset.qrels[qid] for qid in qids}
                if noise_key is not None and variants is None:
                    noise_dir = work / "noise" / noise_key
                    noise_manifest = write_noise_run(
                        noise_dir, queries, "test", run.noise, vocabulary=vocabulary
                    )
                    noise_sha256 = noise_manifest["noisy_queries_sha256"]
                    with (noise_dir / "noisy_queries.jsonl").open(encoding="utf-8") as stream:
                        variants = {row["qid"]: row for row in map(json.loads, stream)}

                candidate = candidates[run.model_id]
                key = _index_key(candidate.analyzer)
                if key not in indexes:
                    index_path = selected_path.parent / "indexes" / key / "index.json"
                    if _sha256(index_path) != index_hashes.get(key):
                        raise ValueError(f"E0 index checksum mismatch: {index_path}")
                    indexes[key] = BatchScorer(load_index(index_path))
                scorer = indexes[key]
                ranking_path = work / "runs" / f"{run.run_id}.jsonl"
                rankings, latency, oov = _rank_queries(ranking_path, queries, variants, candidate, scorer)
                result = evaluate(rankings, qrels)
                if run.experiment_id == "E1":
                    baseline_maps[run.model_id, "test"] = result.mean_ap
                    subset_rankings = protocol.e4_clean_rankings(dataset.queries, rankings)
                    subset_qrels = {qid: dataset.qrels[qid] for qid in subset_rankings}
                    baseline_maps[run.model_id, "e4_eligible"] = evaluate(subset_rankings, subset_qrels).mean_ap
                baseline = baseline_maps[run.model_id, run.query_set]
                latencies = sorted(latency.values())
                summaries.append({
                    "run_id": run.run_id, "experiment_id": run.experiment_id, "model_id": run.model_id,
                    "model": candidate.scorer, "analyzer": candidate.analyzer.kind,
                    "noise_type": run.noise.noise_type if run.noise else "clean",
                    "rate": run.noise.target_rate if run.noise else 0,
                    "fixed_k": run.noise.target_k if run.noise else None,
                    "seed": run.noise.seed if run.noise else None,
                    "n_queries": result.n_queries, "excluded_queries": result.excluded_query_count,
                    "MAP": result.mean_ap, "P@5": result.mean_precision_at_5, "P@10": result.mean_precision_at_k,
                    "Recall@10": result.mean_recall_at_k, "nDCG@10": result.mean_ndcg_at_k,
                    "no_result_rate": result.no_result_rate, "baseline_MAP": baseline,
                    "drop": baseline - result.mean_ap if baseline is not None and result.mean_ap is not None else None,
                    "latency_ms_median": median(latencies) if latencies else None,
                    "latency_ms_p95": latencies[ceil(0.95 * len(latencies)) - 1] if latencies else None,
                })
                per_query.extend({
                    "run_id": run.run_id, "qid": qid, "AP": row.ap, "P@5": row.precision_at_5,
                    "P@10": row.precision_at_k, "Recall@10": row.recall_at_k, "nDCG@10": row.ndcg_at_k,
                    "no_results": row.no_results, "latency_ms": latency[qid], "oov_count": oov[qid],
                } for qid, row in result.per_query.items())
                manifest = {
                    "run_id": run.run_id, "split": "test", "query_set": run.query_set,
                    "query_ids_sha256": _json_digest(list(qids)),
                    "config": asdict(candidate), "noise": asdict(run.noise) if run.noise else None,
                    "index_sha256": index_hashes[key], "data_sha256": hashes,
                    "noise_key": noise_key, "noise_sha256": noise_sha256,
                    "ranking_sha256": _sha256(ranking_path), "source_code_sha256": code_hash,
                    "selected_config_sha256": selection_hash,
                    "top_k": None, "metric_cutoff": result.k, "query_count": len(qids),
                    "excluded_query_ids": result.excluded_query_ids,
                    "baseline_run_id": f"E1-{run.model_id}-clean",
                    "python": platform.python_version(), "platform": platform.platform(), "threads": 1,
                    "scoring_backend": "numpy_sparse_postings",
                }
                (work / "manifests" / f"{run.run_id}.json").write_text(
                    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
                )
        _csv(work / "metrics" / "per_query.csv", per_query)
        _csv(work / "metrics" / "summary.csv", summaries)
        work.rename(output)
