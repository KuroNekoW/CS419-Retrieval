"""Evaluate complete rankings against binary relevance judgments."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import log2
from statistics import fmean


@dataclass(frozen=True)
class QueryMetrics:
    ap: float
    precision_at_5: float
    precision_at_k: float
    recall_at_k: float
    ndcg_at_k: float
    no_results: bool


@dataclass(frozen=True)
class EvaluationResult:
    k: int
    per_query: dict[str, QueryMetrics]
    excluded_query_ids: tuple[str, ...]
    mean_ap: float | None
    mean_precision_at_5: float | None
    mean_precision_at_k: float | None
    mean_recall_at_k: float | None
    mean_ndcg_at_k: float | None
    no_result_rate: float | None

    @property
    def n_queries(self) -> int:
        return len(self.per_query)

    @property
    def excluded_query_count(self) -> int:
        return len(self.excluded_query_ids)


def _evaluate_query(ranking: Iterable[str], relevant: set[str], k: int) -> QueryMetrics:
    seen: set[str] = set()
    matched = 0
    matched_at_5 = 0
    matched_at_k = 0
    precision_sum = 0.0
    dcg = 0.0
    for rank, doc_id in enumerate(ranking, 1):
        if doc_id in seen:
            raise ValueError(f"duplicate document in ranking: {doc_id!r}")
        seen.add(doc_id)
        if doc_id in relevant:
            matched += 1
            precision_sum += matched / rank
            if rank <= 5:
                matched_at_5 += 1
            if rank <= k:
                matched_at_k += 1
                dcg += 1 / log2(rank + 1)

    ideal_dcg = sum(1 / log2(rank + 1) for rank in range(1, min(k, len(relevant)) + 1))
    return QueryMetrics(
        ap=precision_sum / len(relevant),
        precision_at_5=matched_at_5 / 5,
        precision_at_k=matched_at_k / k,
        recall_at_k=matched_at_k / len(relevant),
        ndcg_at_k=dcg / ideal_dcg,
        no_results=not seen,
    )


def evaluate(
    rankings: Mapping[str, Iterable[str]],
    qrels: Mapping[str, Mapping[str, int]],
    k: int = 10,
) -> EvaluationResult:
    """Use qrels as the query cohort and pass ordered IDs for all positive finite hits.

    AP uses the full ranking. Missing rankings are empty and queries without
    positive qrels are excluded. Aggregate values are None for an empty cohort.
    """
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError("k must be a positive integer")
    unknown = rankings.keys() - qrels.keys()
    if unknown:
        raise ValueError(f"ranking query ID absent from qrels: {min(unknown)!r}")

    per_query = {}
    excluded = []
    for qid, judgments in sorted(qrels.items()):
        relevant = {doc_id for doc_id, score in judgments.items() if score > 0}
        if not relevant:
            excluded.append(qid)
            continue
        try:
            per_query[qid] = _evaluate_query(rankings.get(qid, ()), relevant, k)
        except ValueError as error:
            raise ValueError(f"query {qid!r}: {error}") from error

    rows = per_query.values()
    return EvaluationResult(
        k=k,
        per_query=per_query,
        excluded_query_ids=tuple(excluded),
        mean_ap=fmean(row.ap for row in rows) if rows else None,
        mean_precision_at_5=fmean(row.precision_at_5 for row in rows) if rows else None,
        mean_precision_at_k=fmean(row.precision_at_k for row in rows) if rows else None,
        mean_recall_at_k=fmean(row.recall_at_k for row in rows) if rows else None,
        mean_ndcg_at_k=fmean(row.ndcg_at_k for row in rows) if rows else None,
        no_result_rate=fmean(row.no_results for row in rows) if rows else None,
    )
