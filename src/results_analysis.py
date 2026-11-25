"""Build report tables and figures from the archived SciFact experiment."""

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean, stdev
from tempfile import TemporaryDirectory

import matplotlib
import yaml

from .case_analysis import write_cases
from .data_loader import DEFAULT_PATH

matplotlib.use("Agg")
from matplotlib import pyplot as plt


ROOT = Path("data/processed/p14-scifact-20261125")
DATASET_STATS = Path("data/processed/scifact/dataset_stats.csv")
METRICS = ("MAP", "P@5", "P@10", "Recall@10", "nDCG@10", "no_result_rate")
MODELS = {"M1": "VSM word", "M2": "BM25 word", "M3": "VSM char", "M4": "BM25 char"}
COLORS = ("#0072B2", "#D55E00", "#009E73", "#8A5897")
OPERATIONS = ("deletion", "insertion", "substitution", "transposition")


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def aggregate_runs(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        key = tuple(row[field] for field in ("experiment_id", "model_id", "noise_type", "rate", "fixed_k"))
        groups[key].append(row)

    aggregates = []
    for (experiment, model, noise, rate, fixed_k), runs in sorted(groups.items()):
        seeds = sorted(row["seed"] for row in runs)
        if seeds != ([""] if experiment == "E1" else ["42", "43", "44", "45", "46"]):
            raise ValueError(f"incomplete or duplicate seeds in {experiment}/{model}/{noise}/{rate}/{fixed_k}")
        baseline = float(runs[0]["baseline_MAP"])
        n_queries = int(runs[0]["n_queries"])
        if any(float(row["baseline_MAP"]) != baseline or int(row["n_queries"]) != n_queries for row in runs):
            raise ValueError(f"mixed query cohorts in {experiment}/{model}")
        summary = {
            "experiment_id": experiment, "model_id": model, "model": MODELS[model],
            "noise_type": noise, "rate": rate, "fixed_k": fixed_k, "n_queries": n_queries,
            "n_runs": len(runs), "baseline_MAP": baseline,
        }
        for metric in METRICS:
            values = [float(row[metric]) for row in runs]
            if any(not 0 <= value <= 1 for value in values):
                raise ValueError(f"invalid {metric} in {experiment}/{model}")
            summary[f"{metric}_mean"] = fmean(values)
            summary[f"{metric}_std"] = stdev(values) if len(values) > 1 else None
        drop = baseline - summary["MAP_mean"]
        if not math.isclose(drop, fmean(float(row["drop"]) for row in runs), abs_tol=1e-12):
            raise ValueError(f"inconsistent MAP drop in {experiment}/{model}")
        summary["MAP_drop"] = drop
        summary["MAP_drop_relative_pct"] = 100 * drop / baseline if baseline else None
        aggregates.append(summary)
    if len(aggregates) != 44 or len(rows) != 204 or len({row["run_id"] for row in rows}) != 204:
        raise ValueError("expected 204 unique E1–E4 runs and 44 condition/model groups")
    return aggregates


def index_tables(tune_dir: Path, selected: dict) -> list[dict]:
    configs = {
        (cfg["analyzer"]["kind"], cfg["analyzer"]["min_df"], cfg["analyzer"]["max_df_ratio"])
        for cfg in selected.values()
    }
    rows = []
    for path in sorted((tune_dir / "indexes").glob("*/index_stats.csv")):
        row, = read_csv(path)
        vocab = json.loads((path.parent / f'vocabulary_{row["analyzer"]}_stats.json').read_bytes())
        config = vocab.pop("analyzer")
        key = (config["kind"], config["min_df"], config["max_df_ratio"])
        if key in configs:
            rows.append({**row, "min_df": config["min_df"], "max_df_ratio": config["max_df_ratio"],
                         **vocab, "size_MiB": int(row["bytes"]) / 2**20})
    if len(rows) != len(configs):
        raise ValueError("selected index or vocabulary stats are missing")
    return rows


def _plot(figures: Path, aggregates: list[dict], baselines: list[dict], indexes: list[dict]) -> None:
    def save(fig, name):
        fig.savefig(figures / f"{name}.png", dpi=180)
        plt.close(fig)

    lookup = {(r["experiment_id"], r["model_id"], r["noise_type"], r["rate"] or r["fixed_k"]): r
              for r in aggregates}
    n = baselines[0]["n_queries"]
    with plt.rc_context({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False}):
        fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
        for (model, label), color in zip(MODELS.items(), COLORS, strict=True):
            values = [lookup["E1", model, "clean", "0"]] + [
                lookup["E2", model, "mixed", str(rate)] for rate in (0.1, 0.2, 0.3, 0.5)
            ]
            ax.errorbar([0, 10, 20, 30, 50], [v["MAP_mean"] for v in values],
                        yerr=[v["MAP_std"] or 0 for v in values], label=label,
                        color=color, marker="o", capsize=3)
        ax.set(title=f"E1–E2 · Mixed spelling noise (n={n})", xlabel="Target token edit rate (%)",
               ylabel="MAP", xticks=[0, 10, 20, 30, 50])
        ax.grid(axis="y", alpha=0.23)
        ax.legend(title="Mean ± sample SD · 5 seeds for E2", frameon=False)
        save(fig, "mixed_rate_map")

        for experiment, levels, xlabel, filename in (
            ("E3", OPERATIONS, "Edit operation at 20% target rate", "error_type_drop"),
            ("E4", ("1", "2"), "Edited tokens per query", "fixed_edits_drop"),
        ):
            fig, ax = plt.subplots(figsize=(8.5, 4.5), layout="constrained")
            for i, ((model, label), color) in enumerate(zip(MODELS.items(), COLORS, strict=True)):
                values = [lookup[experiment, model, level, "0.2"] if experiment == "E3"
                          else lookup[experiment, model, "mixed", level] for level in levels]
                ax.bar([x + (i - 1.5) * 0.19 for x in range(len(levels))],
                       [100 * v["MAP_drop"] for v in values], 0.18,
                       yerr=[100 * v["MAP_std"] for v in values], capsize=2, label=label, color=color)
            cohort = values[0]["n_queries"]
            ax.set(title=f"{experiment} · MAP decrease from paired clean baseline (n={cohort})",
                   xlabel=xlabel, ylabel="MAP decrease (percentage points)",
                   xticks=range(len(levels)), xticklabels=levels)
            ax.axhline(0, color="#444444", linewidth=0.8)
            ax.grid(axis="y", alpha=0.23)
            ax.legend(title="Mean ± sample SD · 5 seeds", frameon=False, ncols=4,
                      loc="upper center", bbox_to_anchor=(0.5, -0.17))
            save(fig, filename)

        fig, axes = plt.subplots(1, 2, figsize=(8, 4), layout="constrained")
        labels = [f'{row["analyzer"]} (DF ≥ {row["min_df"]})' for row in indexes]
        for ax, values, title, ylabel in (
            (axes[0], [row["size_MiB"] for row in indexes], "Index storage", "MiB"),
            (axes[1], [float(row["build_seconds"]) for row in indexes], "Index build", "Seconds"),
        ):
            bars = ax.bar(labels, values, color="#0072B2", width=0.55)
            ax.bar_label(bars, fmt="%.2f", padding=3)
            ax.set(title=title, ylabel=ylabel, ylim=(0, max(values) * 1.2))
        save(fig, "index_cost")

        fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
        positions = range(len(baselines))
        for offset, key, label, color in (
            (-0.19, "latency_ms_median", "Median", "#0072B2"),
            (0.19, "latency_ms_p95", "P95", "#D55E00"),
        ):
            ax.bar([i + offset for i in positions], [float(row[key]) for row in baselines], 0.36,
                   label=label, color=color)
        ax.set(title=f"E1 · Clean-query latency (n={n})", ylabel="Milliseconds per query",
               xticks=positions, xticklabels=[MODELS[row["model_id"]] for row in baselines])
        ax.legend(frameon=False)
        save(fig, "query_latency")


def analyze_results(run: Path, data: Path, stats: Path, output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"{output} already exists")
    evaluation = run / "E1-E4"
    rows = read_csv(evaluation / "metrics" / "summary.csv")
    aggregates = aggregate_runs(rows)
    baselines = sorted((r for r in rows if r["experiment_id"] == "E1"), key=lambda row: row["model_id"])
    tune_dir = run / "E0"
    selected = yaml.safe_load((tune_dir / "selected_config.yaml").read_bytes())["models"]
    indexes = index_tables(tune_dir, selected)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as temporary:
        staged = Path(temporary) / "analysis"
        figures = staged / "figures"
        figures.mkdir(parents=True)
        write_csv(staged / "aggregate.csv", aggregates)
        write_csv(staged / "baseline.csv", baselines)
        write_csv(staged / "tuning.csv", read_csv(tune_dir / "tuning.csv"))
        write_csv(staged / "index_cost.csv", indexes)
        write_csv(staged / "dataset_stats.csv", read_csv(stats))
        write_cases(evaluation, data, tune_dir, selected, staged)
        _plot(figures, aggregates, baselines, indexes)
        staged.rename(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=ROOT)
    parser.add_argument("--data", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--dataset-stats", type=Path, default=DATASET_STATS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        analyze_results(args.run, args.data, args.dataset_stats, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(args.output)


if __name__ == "__main__":
    main()
