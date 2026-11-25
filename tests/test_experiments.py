from collections import Counter, defaultdict

import pytest
import yaml

from src.experiments import DEFAULT_CONFIG, experiment_counts, load_protocol
from src.noise_generator import OPERATIONS, generate_noise


def test_protocol_matrix_shares_noise_and_has_unique_runs():
    protocol = load_protocol()
    assert experiment_counts(protocol) == {"E0": 20, "E1": 4, "E2": 80, "E3": 80, "E4": 40}
    assert len({run.run_id for run in protocol.test_runs}) == 204
    shared = defaultdict(set)
    conditions = defaultdict(set)
    for run in protocol.test_runs:
        if run.noise is not None:
            shared[run.noise_key].add(run.model_id)
            conditions[run.experiment_id].add(run.noise)
        else:
            assert run.experiment_id == "E1" and run.noise_key is None
        assert run.query_set == ("e4_eligible" if run.experiment_id == "E4" else "test")
    assert len(shared) == 50
    assert all(models == {"M1", "M2", "M3", "M4"} for models in shared.values())
    assert {item.target_rate for item in conditions["E2"]} == {0.1, 0.2, 0.3, 0.5}
    assert {item.noise_type for item in conditions["E3"]} == set(OPERATIONS)
    assert {item.target_rate for item in conditions["E3"]} == {0.2}
    assert {item.target_k for item in conditions["E4"]} == {1, 2}
    for group in conditions.values():
        assert set(Counter(item.seed for item in group)) == set(range(42, 47))


def test_dev_selection_requires_complete_e0_scores_and_breaks_ties():
    protocol = load_protocol()
    scores = dict.fromkeys((candidate.candidate_id for candidate in protocol.dev_candidates), 0.4)
    winners = protocol.select_dev_winners(scores)
    assert winners["M1"].analyzer.min_df == 1
    assert winners["M2"].k1 == 1.2 and winners["M2"].b == 0.75
    nondefault = protocol.dev_candidates[-1]
    scores[nondefault.candidate_id] = 0.5
    assert protocol.select_dev_winners(scores)["M4"] == nondefault
    scores["E1-M4-clean"] = 0.9
    with pytest.raises(ValueError, match="each E0 candidate"):
        protocol.select_dev_winners(scores)


def test_e4_uses_same_cohort_and_same_clean_rankings_for_both_levels():
    protocol = load_protocol()
    queries = {"003": "Cardiac disease", "02": "alpha DNA2", "01": "gene expression level"}
    clean = {"003": [], "02": ["D2"], "01": ["D1"]}
    cohort = protocol.e4_query_ids(queries)
    assert cohort == ("003", "01")
    assert protocol.e4_clean_rankings(queries, clean) == {"003": [], "01": ["D1"]}
    with pytest.raises(ValueError, match="all test query IDs"):
        protocol.e4_clean_rankings(queries, {"01": ["D1"]})
    for run in protocol.test_runs:
        if run.experiment_id == "E4":
            for qid in cohort:
                variant = generate_noise(qid, queries[qid], "test", run.noise)
                assert variant["edited_count"] == run.noise.target_k


@pytest.mark.parametrize(
    ("section", "key", "value", "message"),
    [
        ("E0", "split", "test", "select on train MAP"),
        ("test", "seeds", [42], "match the E2–E4 protocol"),
        ("evaluation", "top_k", 10, "requires full rankings"),
    ],
)
def test_config_rejects_protocol_drift(tmp_path, section, key, value, message):
    config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config[section][key] = value
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_protocol(path)
