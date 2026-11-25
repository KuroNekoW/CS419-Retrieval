import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml


def _run(*args, check=True):
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *map(str, args)],
        check=check, capture_output=True, text=True,
    )


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_tune_and_experiment_cli_end_to_end(tmp_path: Path):
    data, tuning, output = (tmp_path / name for name in ("data", "tuning", "experiment"))
    header = "query-id\tcorpus-id\tscore\n"
    (data / "qrels").mkdir(parents=True)
    (data / "corpus.jsonl").write_text(
        '{"_id":"D1","title":"Heart health","text":"Cardiac function study"}\n'
        '{"_id":"D2","title":"Mars geology","text":"Mineral samples"}\n',
        encoding="utf-8",
    )
    (data / "queries.jsonl").write_text(
        '{"_id":"train1","text":"Cardiac function"}\n'
        '{"_id":"test1","text":"Heart health"}\n'
        '{"_id":"test2","text":"zzzzzz"}\n',
        encoding="utf-8",
    )
    (data / "qrels" / "train.tsv").write_text(header + "train1\tD1\t1\n", encoding="utf-8")

    # E0 must succeed before test judgments are available.
    _run("tune", "--data", data, "--output", tuning, "--split", "train")
    selected_path = tuning / "selected_config.yaml"
    selected = yaml.safe_load(selected_path.read_bytes())
    assert selected["candidate_count"] == 20
    assert set(selected["models"]) == {"M1", "M2", "M3", "M4"}
    assert "qrels/test.tsv" not in selected["dev_data_sha256"]
    with (tuning / "tuning.csv").open(encoding="utf-8", newline="") as stream:
        candidates = list(csv.DictReader(stream))
    assert len(candidates) == 20 and sum(row["selected"] == "True" for row in candidates) == 4

    (data / "qrels" / "test.tsv").write_text(
        header + "test1\tD1\t1\ntest2\tD2\t1\n", encoding="utf-8"
    )
    _run("experiment", "--data", data, "--selected-config", selected_path, "--output", output)
    ranking_files = list((output / "runs").glob("*.jsonl"))
    assert len(ranking_files) == 204
    (hit, empty) = _read_jsonl(output / "runs" / "E1-M1-clean.jsonl")
    assert hit["ranking"][0]["doc_id"] == "D1" and hit["ranking"][0]["rank"] == 1
    assert empty == {"qid": "test2", "variant_id": "test/clean/test2", "ranking": []}
    with (output / "metrics" / "summary.csv").open(encoding="utf-8", newline="") as stream:
        summary = {row["run_id"]: row for row in csv.DictReader(stream)}
    assert Counter(row["experiment_id"] for row in summary.values()) == {
        "E1": 4, "E2": 80, "E3": 80, "E4": 40,
    }
    assert float(summary["E1-M1-clean"]["MAP"]) == 0.5
    assert float(summary["E1-M1-clean"]["no_result_rate"]) == 0.5
    for row in summary.values():
        if row["experiment_id"] == "E4":
            assert row["n_queries"] == "1" and float(row["baseline_MAP"]) == 1
    with (output / "metrics" / "per_query.csv").open(encoding="utf-8", newline="") as stream:
        query_metrics = {(row["run_id"], row["qid"]): row for row in csv.DictReader(stream)}
    empty_metrics = query_metrics["E1-M1-clean", "test2"]
    assert empty_metrics["no_results"] == "True"
    assert float(empty_metrics["AP"]) == 0 and int(empty_metrics["oov_count"]) > 0

    paths = (output / "noise").rglob("noisy_queries.jsonl")
    assert len(list(paths)) == 50
    run_ids = [f"E2-M{i}-mixed-rate0.2-seed42" for i in range(1, 5)]
    hashes = set()
    for run_id in run_ids:
        manifest = json.loads((output / "manifests" / f"{run_id}.json").read_text(encoding="utf-8"))
        hashes.add(manifest["noise_sha256"])
        noise_path = output / "noise" / manifest["noise_key"] / "noisy_queries.jsonl"
        assert manifest["noise_sha256"] == hashlib.sha256(noise_path.read_bytes()).hexdigest()
        ranking_path = output / "runs" / f"{run_id}.jsonl"
        assert manifest["ranking_sha256"] == hashlib.sha256(ranking_path.read_bytes()).hexdigest()
        assert [row["variant_id"] for row in _read_jsonl(ranking_path)] == [
            row["variant_id"] for row in _read_jsonl(noise_path)
        ]
    assert len(hashes) == 1

    retry = _run(
        "experiment", "--data", data, "--selected-config", selected_path, "--output", output, check=False
    )
    assert retry.returncode == 1 and "already exists" in retry.stderr
    tuning_csv = tuning / "tuning.csv"
    original = tuning_csv.read_bytes()
    try:
        tuning_csv.write_text("tampered\n", encoding="utf-8")
        rejected = tmp_path / "rejected"
        trial = _run(
            "experiment", "--data", data, "--selected-config", selected_path, "--output", rejected, check=False,
        )
        assert trial.returncode == 1 and "checksum mismatch" in trial.stderr
        assert not rejected.exists()
    finally:
        tuning_csv.write_bytes(original)
