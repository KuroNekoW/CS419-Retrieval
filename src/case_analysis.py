"""Extract paired query examples from archived rankings."""

import csv
import json
from pathlib import Path

from .data_loader import load_dataset
from .preprocessing import AnalyzerConfig, analyze

CASE_RUNS = {
    (model, condition): (
        f"E1-{model}-clean" if condition == "clean" else f"E2-{model}-mixed-rate0.2-seed42"
    )
    for model in ("M2", "M4")
    for condition in ("clean", "noisy")
}


def _read_selected(path: Path, qids: set[str]) -> dict[str, dict]:
    rows = {}
    with path.open("rb") as stream:
        for line in stream:
            header, separator, _ = line.partition(b',"ranking":')
            row = json.loads(header + b"}" if separator else line)
            if row["qid"] in qids:
                rows[row["qid"]] = json.loads(line) if separator else row
                if rows.keys() == qids:
                    return rows
    raise ValueError(f"{path}: missing query IDs {sorted(qids - rows.keys())}")


def _vocabulary(tune_dir: Path, config: AnalyzerConfig) -> set[str]:
    for path in (tune_dir / "indexes").glob(f"*/vocabulary_{config.kind}_stats.json"):
        recorded = AnalyzerConfig(**json.loads(path.read_bytes())["analyzer"])
        if recorded == config:
            selected = path.with_name(f"vocabulary_{config.kind}_selected.tsv")
            with selected.open(encoding="utf-8", newline="") as stream:
                return {row["term"] for row in csv.DictReader(stream, delimiter="\t")}
    raise ValueError(f"selected vocabulary not found for {config}")


def _write_case_table(output: Path, cases: list[dict]) -> None:
    rows = []
    for case in cases:
        for model, detail in case["models"].items():
            clean, noisy = detail["clean"], detail["noisy"]
            rows.append({
                "qid": case["qid"], "group": case["group"], "model_id": model,
                "original": case["original"], "noisy": case["noisy"],
                "edits": json.dumps(case["edits"], ensure_ascii=False),
                "relevant_doc_ids": " ".join(case["relevant_doc_ids"]),
                "AP_clean": clean["AP"], "AP_noisy": noisy["AP"],
                "OOV_clean": len(clean["OOV"]), "OOV_noisy": len(noisy["OOV"]),
                "lost_terms": " ".join(detail["lost_terms"]),
                "retained_terms": " ".join(detail["retained_terms"]),
                "clean_relevant_ranks": json.dumps(clean["relevant_ranks"]),
                "noisy_relevant_ranks": json.dumps(noisy["relevant_ranks"]),
                "clean_top5": " ".join(hit["doc_id"] for hit in clean["top5"]),
                "noisy_top5": " ".join(hit["doc_id"] for hit in noisy["top5"]),
            })
    with (output / "cases.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_cases(evaluation: Path, data: Path, tune_dir: Path, selected: dict, output: Path) -> None:
    with (evaluation / "metrics" / "per_query.csv").open(encoding="utf-8", newline="") as stream:
        metrics = {(row["run_id"], row["qid"]): row for row in csv.DictReader(stream)
                   if row["run_id"] in CASE_RUNS.values()}

    def delta(qid: str) -> float:
        return float(metrics[CASE_RUNS["M2", "noisy"], qid]["AP"]) - float(metrics[CASE_RUNS["M2", "clean"], qid]["AP"])

    dataset = load_dataset(data, "test")
    decreases = sorted((qid for qid in dataset.queries if delta(qid) < 0), key=lambda qid: (delta(qid), qid))[:3]
    stable_or_improved = sorted(
        (qid for qid in dataset.queries if delta(qid) >= 0), key=lambda qid: (-delta(qid), qid)
    )[:3]
    qids = set(decreases + stable_or_improved)
    if not qids:
        raise ValueError("no query cases available")
    rankings = {label: _read_selected(evaluation / "runs" / f"{run_id}.jsonl", qids)
                for label, run_id in CASE_RUNS.items()}
    noise_path = evaluation / "noise/test/test/mixed-rate0.2-seed42/noisy_queries.jsonl"
    variants = _read_selected(noise_path, qids)
    configs = {model: AnalyzerConfig(**selected[model]["analyzer"]) for model in ("M2", "M4")}
    vocabularies = {model: _vocabulary(tune_dir, config) for model, config in configs.items()}
    cases = []
    for qid in decreases + stable_or_improved:
        variant = variants[qid]
        if dataset.queries[qid] != variant["original"]:
            raise ValueError(f"{qid}: original query mismatch")
        relevant = sorted(doc_id for doc_id, score in dataset.qrels[qid].items() if score > 0)
        details = {}
        for model, config in configs.items():
            original_terms = analyze(variant["original"], config)
            noisy_terms = analyze(variant["noisy"], config)
            vocab = vocabularies[model]
            before, after = set(original_terms) & vocab, set(noisy_terms) & vocab
            model_details = {
                "lost_terms": sorted(before - after),
                "retained_terms": sorted(before & after),
                "added_terms": sorted(after - before),
            }
            for condition, terms in (("clean", original_terms), ("noisy", noisy_terms)):
                row = rankings[model, condition][qid]
                if condition == "noisy" and row["variant_id"] != variant["variant_id"]:
                    raise ValueError(f"{qid}: noise variant mismatch for {model}")
                hits = row["ranking"]
                positions = {hit["doc_id"]: hit["rank"] for hit in hits}
                top5 = [{**hit, "title": dataset.corpus[hit["doc_id"]].title,
                         "positive_qrel": hit["doc_id"] in relevant} for hit in hits[:5]]
                metric = metrics[CASE_RUNS[model, condition], qid]
                oov = [term for term in terms if term not in vocab]
                if len(oov) != int(metric["oov_count"]):
                    raise ValueError(f"{qid}: OOV mismatch for {model}/{condition}")
                model_details[condition] = {
                    "AP": float(metric["AP"]), "OOV": oov, "top5": top5,
                    "relevant_ranks": {doc_id: positions.get(doc_id) for doc_id in relevant},
                }
            details[model] = model_details
        candidate = next((hit for hit in details["M4"]["noisy"]["top5"] if not hit["positive_qrel"]), None)
        overlap_example = None
        if candidate:
            document = dataset.corpus[candidate["doc_id"]]
            config = configs["M4"]
            terms = set(analyze(variant["noisy"], config))
            shared = terms & set(analyze(document.content, config)) & vocabularies["M4"]
            overlap_example = {
                "doc_id": candidate["doc_id"], "rank": candidate["rank"],
                "shared_char_terms": sorted(shared),
            }
        cases.append({
            "qid": qid, "group": "decrease" if qid in decreases else "stable_or_improved",
            "variant_id": variant["variant_id"], "original": variant["original"], "noisy": variant["noisy"],
            "edits": variant["edits"], "relevant_doc_ids": relevant,
            "word_AP_change": delta(qid), "models": details, "char_nonpositive_hit_overlap": overlap_example,
        })
    (output / "cases.json").write_text(json.dumps({
        "selection": "M2, mixed 20%, seed 42. Up to three most negative and three largest nonnegative AP changes; qid breaks ties.",
        "cases": cases,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_case_table(output, cases)
