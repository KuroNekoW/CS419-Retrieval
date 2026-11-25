from math import log2

import ir_measures
import pytest

from src.evaluation import evaluate


def test_specification_examples_and_macro_average():
    result = evaluate(
        {"a": ["D1", "D2", "D3"], "b": ["D2", "D4", "D1", "D5", "D3"]},
        {"a": {"D1": 1, "D3": 1}, "b": {"D1": 1, "D3": 1}},
    )
    assert result.n_queries == 2
    first, second = result.per_query.values()
    assert first.ap == pytest.approx(5 / 6)
    assert second.ap == pytest.approx(11 / 30)
    assert result.mean_ap == pytest.approx(0.6)
    assert result.mean_precision_at_5 == pytest.approx(0.4)
    assert result.mean_precision_at_k == pytest.approx(0.2)
    assert result.mean_recall_at_k == 1
    ideal = 1 + 1 / log2(3)
    assert first.ndcg_at_k == pytest.approx((1 + 1 / log2(4)) / ideal)
    assert second.ndcg_at_k == pytest.approx((1 / log2(4) + 1 / log2(6)) / ideal)
    assert result.mean_ndcg_at_k == pytest.approx((first.ndcg_at_k + second.ndcg_at_k) / 2)
    assert result.no_result_rate == 0


def test_full_ap_counts_hits_past_cutoff_and_missed_relevance():
    ranking = [f"unjudged{i}" for i in range(10)] + ["relevant"]
    qrels = {"q": {"relevant": 2, "missed": 1, "irrelevant": 0}}
    result = evaluate({"q": ranking}, qrels)
    assert result.mean_ap == pytest.approx(1 / 22)
    assert result.mean_precision_at_5 == result.mean_precision_at_k == 0
    assert result.mean_recall_at_k == result.mean_ndcg_at_k == 0
    assert result.no_result_rate == 0

    at_one = evaluate({"q": ["relevant"]}, qrels, k=1)
    assert at_one.mean_precision_at_k == at_one.mean_ndcg_at_k == 1
    assert at_one.mean_recall_at_k == 0.5


def test_missing_ranking_is_empty_and_no_positive_qrels_are_excluded():
    result = evaluate(
        {"hit": ["D1"], "explicit-empty": [], "excluded": ["D1"]},
        {"hit": {"D1": 1}, "explicit-empty": {"D1": 1}, "missing": {"D1": 1}, "excluded": {"D1": 0}},
    )
    assert result.n_queries == 3
    assert result.excluded_query_count == 1
    assert result.excluded_query_ids == ("excluded",)
    for qid in ("explicit-empty", "missing"):
        row = result.per_query[qid]
        assert row.no_results
        assert row.ap == row.precision_at_5 == row.precision_at_k == row.recall_at_k == row.ndcg_at_k == 0
    assert result.mean_ap == pytest.approx(1 / 3)
    assert result.no_result_rate == pytest.approx(2 / 3)


def test_empty_evaluation_is_undefined_and_rejects_invalid_inputs():
    result = evaluate({}, {"unjudged": {}})
    assert result.n_queries == 0
    assert result.excluded_query_count == 1
    assert result.mean_ap is result.no_result_rate is None
    with pytest.raises(ValueError, match="positive integer"):
        evaluate({}, {}, k=0)
    with pytest.raises(ValueError, match="ranking query ID absent"):
        evaluate({"typo": ["D1"]}, {"qid": {"D1": 1}})
    with pytest.raises(ValueError, match="query 'qid': duplicate document"):
        evaluate({"qid": ["D1", "D1"]}, {"qid": {"D1": 1}})


def test_metrics_agree_with_ir_measures():
    rankings = {
        "q1": ["miss", "yes", *[f"d{i}" for i in range(9)], "late"],
        "q2": [],
        "q3": ["yes", "miss"],
        "excluded": [],
    }
    qrels = {
        "q1": {"yes": 2, "late": 1, "never_returned": 1},
        "q2": {"yes": 1},
        "q3": {"yes": 1},
        "excluded": {"miss": 0},
    }
    observed = evaluate(rankings, qrels)
    binary_qrels = {qid: {doc: int(score > 0) for doc, score in qrels[qid].items()} for qid in observed.per_query}
    scored = {
        qid: {doc: -rank for rank, doc in enumerate(rankings[qid], 1)}
        for qid in observed.per_query
    }
    ap, p5, p10, recall, ndcg = (
        ir_measures.AP, ir_measures.P @ 5, ir_measures.P @ 10,
        ir_measures.R @ 10, ir_measures.nDCG @ 10,
    )
    measures = [ap, p5, p10, recall, ndcg]
    reference = ir_measures.calc_aggregate(measures, binary_qrels, scored)
    for metric, actual in zip(measures, (
        observed.mean_ap, observed.mean_precision_at_5, observed.mean_precision_at_k,
        observed.mean_recall_at_k, observed.mean_ndcg_at_k,
    ), strict=True):
        assert actual == pytest.approx(reference[metric])
    for row in ir_measures.iter_calc(measures, binary_qrels, scored):
        actual = observed.per_query[row.query_id]
        scores = {
            ap: actual.ap, p5: actual.precision_at_5, p10: actual.precision_at_k,
            recall: actual.recall_at_k, ndcg: actual.ndcg_at_k,
        }
        assert scores[row.measure] == pytest.approx(row.value)
