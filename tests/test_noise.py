import hashlib
import json

import pytest

from src.noise_generator import OPERATIONS, NoiseCondition, generate_noise, write_noise_run


@pytest.mark.parametrize("operation", OPERATIONS)
def test_exact_edit_and_original_text(operation):
    condition = NoiseCondition(operation, 42, target_k=1)
    original = "  GENE,\tIL6_ABC 123 naïve cafe\u0301! "
    record = generate_noise("007", original, "test", condition)
    edit, = record["edits"]
    assert record["qid"] == "007"
    assert record["original"] == original
    assert record["eligible_count"] == 1
    assert record["edited_count"] == 1
    assert edit["token_index"] == 0
    assert edit["operation"] == operation
    new_word = edit["modified_token"]
    assert new_word.isupper()
    assert record["noisy"] == original.replace("GENE", new_word)
    pos = edit["character_position"]
    word = edit["original_token"]
    assert word != new_word
    if operation == "deletion":
        assert new_word == word[:pos] + word[pos + 1 :]
    elif operation == "insertion":
        assert word == new_word[:pos] + new_word[pos + 1 :]
    elif operation == "substitution":
        assert len(word) == len(new_word)
        assert word[:pos] == new_word[:pos] and word[pos + 1 :] == new_word[pos + 1 :]
    else:
        assert new_word == word[:pos] + word[pos + 1] + word[pos] + word[pos + 2 :]


def test_rounding_zero_and_insufficient_tokens():
    original = "alpha beta gamma delta epsilon"
    for rate, changed in [(0, 0), (0.09, 0), (0.1, 1), (0.5, 3)]:
        record = generate_noise("1", original, "train", NoiseCondition("mixed", 42, target_rate=rate))
        assert record["edited_count"] == changed
        assert record["actual_rate"] == changed / 5
        assert len({edit["token_index"] for edit in record["edits"]}) == changed
        assert (record["noisy"] == original) == (changed == 0)
    fixed = NoiseCondition("mixed", 42, target_k=2)
    assert generate_noise("1", "alpha beta", "test", fixed)["edited_count"] == 2
    insufficient = generate_noise("1", "alpha DNA2", "test", fixed)
    assert insufficient["status"] == "insufficient_eligible"
    assert insufficient["noisy"] == "alpha DNA2"


def test_operation_specific_eligibility_and_corpus_flag():
    swap = NoiseCondition("transposition", 42, target_rate=1)
    record = generate_noise("1", "AaA", "test", swap)
    assert record["status"] == "no_eligible"
    assert record["noisy"] == "AaA"
    mixed = NoiseCondition("mixed", 42, target_rate=1)
    edited = generate_noise("1", "AaA", "test", mixed)
    edit, = edited["edits"]
    assert edit["operation"] != "transposition"
    checked = generate_noise("1", "AaA", "test", mixed, vocabulary={edit["modified_token"].lower()})
    assert checked["edits"][0]["matches_corpus_word"] is True


def test_run_order_reproducibility_and_manifest(tmp_path):
    queries = {"2": "one two three four five", "01": "alpha beta", "3": "123"}
    condition = NoiseCondition("mixed", 42, target_rate=0.5)
    first = write_noise_run(tmp_path / "first", queries, "test", condition)
    second = write_noise_run(tmp_path / "second", dict(reversed(list(queries.items()))), "test", condition)
    data = (tmp_path / "first" / "noisy_queries.jsonl").read_bytes()
    assert data == (tmp_path / "second" / "noisy_queries.jsonl").read_bytes()
    assert first == second
    assert hashlib.sha256(data).hexdigest() == first["noisy_queries_sha256"]
    assert [json.loads(line)["qid"] for line in data.splitlines()] == ["01", "2", "3"]
    assert first["changed_query_count"] == 2
    assert first["edited_count_distribution"] == {0: 1, 1: 1, 3: 1}
    another_seed = NoiseCondition("mixed", 43, target_rate=0.5)
    baseline = generate_noise("2", queries["2"], "test", condition)
    variant = generate_noise("2", queries["2"], "test", another_seed)
    assert baseline["variant_id"] != variant["variant_id"]
    assert baseline["noisy"] != variant["noisy"]
    with pytest.raises(FileExistsError):
        write_noise_run(tmp_path / "first", queries, "test", condition)
