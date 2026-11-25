"""Build the experiment schedule and enforce dev selection and shared cohorts."""

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path

import yaml

from .noise_generator import OPERATIONS, NoiseCondition, eligible_token_count
from .preprocessing import AnalyzerConfig

DEFAULT_CONFIG = Path("configs/default.yaml")
MODELS = {
    "M1": ("vsm", "word"),
    "M2": ("bm25", "word"),
    "M3": ("vsm", "char"),
    "M4": ("bm25", "char"),
}


@dataclass(frozen=True)
class DevCandidate:
    model_id: str
    scorer: str
    analyzer: AnalyzerConfig
    k1: float | None
    b: float | None

    @property
    def candidate_id(self) -> str:
        label = f"{self.model_id}-df{self.analyzer.min_df}"
        return label if self.k1 is None else f"{label}-k1-{self.k1:g}-b-{self.b:g}"


@dataclass(frozen=True)
class TestRun:
    experiment_id: str
    model_id: str
    noise: NoiseCondition | None = None

    @property
    def query_set(self) -> str:
        return "e4_eligible" if self.experiment_id == "E4" else "test"

    @property
    def run_id(self) -> str:
        label = "clean" if self.noise is None else self.noise.label
        return f"{self.experiment_id}-{self.model_id}-{label}"

    @property
    def noise_key(self) -> str | None:
        return None if self.noise is None else f"test/{self.query_set}/{self.noise.label}"


@dataclass(frozen=True)
class ExperimentProtocol:
    dev_candidates: tuple[DevCandidate, ...]
    test_runs: tuple[TestRun, ...]
    e4_min_eligible_tokens: int

    def select_dev_winners(self, dev_map: Mapping[str, float]) -> dict[str, DevCandidate]:
        """Select one dev winner per model using complete E0 MAP scores only."""
        expected = {candidate.candidate_id for candidate in self.dev_candidates}
        if dev_map.keys() != expected or any(not 0 <= score <= 1 for score in dev_map.values()):
            raise ValueError("provide a MAP in [0, 1] for each E0 candidate")
        winners: dict[str, DevCandidate] = {}
        for candidate in self.dev_candidates:
            current = winners.get(candidate.model_id)
            if current is None or dev_map[candidate.candidate_id] > dev_map[current.candidate_id]:
                winners[candidate.model_id] = candidate
        return winners

    def e4_query_ids(self, queries: Mapping[str, str]) -> tuple[str, ...]:
        return tuple(
            qid for qid, query in sorted(queries.items())
            if eligible_token_count(query) >= self.e4_min_eligible_tokens
        )

    def e4_clean_rankings(
        self, queries: Mapping[str, str], e1_rankings: Mapping[str, list[str]]
    ) -> dict[str, list[str]]:
        """Reuse full clean rankings for the exact cohort; keep empty rankings."""
        if queries.keys() != e1_rankings.keys():
            raise ValueError("E1 rankings must explicitly cover all test query IDs")
        return {qid: e1_rankings[qid] for qid in self.e4_query_ids(queries)}

    def as_plan(self) -> dict:
        return {
            "E0": {
                "split": "train",
                "condition": "clean",
                "selection_metric": "MAP",
                "tie_break": "first candidate per model in grid order",
                "candidates": [
                    {"candidate_id": candidate.candidate_id, **asdict(candidate)}
                    for candidate in self.dev_candidates
                ],
            },
            "test": {
                "split": "test",
                "model_config_source": "selected_config.yaml from E0",
                "top_k": None,
                "metric_cutoff": 10,
                "E4": {
                    "min_eligible_tokens": self.e4_min_eligible_tokens,
                    "clean_baseline_source": "E1 per-query metrics for matching model and E4 qids",
                },
                "runs": [
                    {
                        **asdict(run),
                        "run_id": run.run_id,
                        "query_set": run.query_set,
                        "noise_key": run.noise_key,
                        "baseline_run_id": f"E1-{run.model_id}-clean",
                    }
                    for run in self.test_runs
                ],
            },
        }


def load_protocol(path: Path = DEFAULT_CONFIG) -> ExperimentProtocol:
    try:
        with path.open(encoding="utf-8") as stream:
            config = yaml.safe_load(stream)
        models = config["models"]
        dev = config["E0"]
        test = config["test"]
        evaluation = config["evaluation"]
        if models != {
            model_id: {"scorer": scorer, "analyzer": analyzer}
            for model_id, (scorer, analyzer) in MODELS.items()
        }:
            raise ValueError("models must match M1–M4")
        if dev["split"] != "train" or dev["metric"] != "MAP" or test["split"] != "test":
            raise ValueError("E0 must select on train MAP and E1–E4 must use test")
        if evaluation != {"top_k": None, "metric_cutoff": 10}:
            raise ValueError("evaluation requires full rankings and cutoff 10")
        if (
            test["seeds"] != list(range(42, 47))
            or test["E2_rates"] != [0.1, 0.2, 0.3, 0.5]
            or test["E3_types"] != list(OPERATIONS)
            or test["E3_rate"] != 0.2
            or test["E4_fixed_tokens"] != [1, 2]
            or test["E4_min_eligible_tokens"] != 2
        ):
            raise ValueError("test conditions must match the E2–E4 protocol in the specification")

        bm25_grid = tuple(product(dev["k1"], dev["b"]))
        if not bm25_grid or any(not 0 <= k1 < float("inf") or not 0 <= b <= 1 for k1, b in bm25_grid):
            raise ValueError("invalid E0 BM25 parameter grid")
        if any(type(value) is not int for value in dev["min_df"]):
            raise ValueError("E0 min_df values must be integers")
        candidates = tuple(
            DevCandidate(model_id, scorer, AnalyzerConfig(analyzer, min_df, dev["max_df_ratio"]), k1, b)
            for model_id, (scorer, analyzer) in MODELS.items()
            for min_df in dev["min_df"]
            for k1, b in (bm25_grid if scorer == "bm25" else ((None, None),))
        )
        if not candidates or len({candidate.candidate_id for candidate in candidates}) != len(candidates):
            raise ValueError("E0 grid must produce nonempty, unique candidates")
        conditions = [
            ("E1", [None]),
            ("E2", [
                NoiseCondition("mixed", seed, target_rate=rate)
                for rate, seed in product(test["E2_rates"], test["seeds"])
            ]),
            ("E3", [
                NoiseCondition(operation, seed, target_rate=test["E3_rate"])
                for operation, seed in product(test["E3_types"], test["seeds"])
            ]),
            ("E4", [
                NoiseCondition("mixed", seed, target_k=count)
                for count, seed in product(test["E4_fixed_tokens"], test["seeds"])
            ]),
        ]
        runs = tuple(
            TestRun(experiment_id, model_id, noise)
            for experiment_id, variants in conditions
            for noise in variants
            for model_id in MODELS
        )
        return ExperimentProtocol(candidates, runs, test["E4_min_eligible_tokens"])
    except (KeyError, TypeError, yaml.YAMLError) as error:
        raise ValueError(f"invalid experiment config {path}: {error}") from error


def write_experiment_plan(protocol: ExperimentProtocol, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(protocol.as_plan(), stream, indent=2)
        stream.write("\n")


def experiment_counts(protocol: ExperimentProtocol) -> dict[str, int]:
    return {"E0": len(protocol.dev_candidates), **Counter(run.experiment_id for run in protocol.test_runs)}
