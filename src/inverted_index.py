"""Build and persist a sparse inverted index for both ranking models."""

import json
from collections import Counter
from dataclasses import asdict, dataclass
from math import log, log1p, sqrt
from pathlib import Path
from tempfile import TemporaryDirectory

from .data_loader import Document
from .preprocessing import AnalyzerConfig, analyze
from .term_selection import TermStats, fit_vocabulary

SCHEMA_VERSION = 1


@dataclass
class InvertedIndex:
    config: AnalyzerConfig
    corpus_sha256: str
    titles: dict[str, str]
    snippets: dict[str, str]
    postings: dict[str, dict[str, int]]
    df: dict[str, int]
    cf: dict[str, int]
    doc_lengths: dict[str, int]
    doc_norms: dict[str, float]
    vsm_idf: dict[str, float]
    bm25_idf: dict[str, float]
    n_docs: int
    avgdl: float


def build_index(
    corpus: dict[str, Document], config: AnalyzerConfig, *, corpus_sha256: str
) -> tuple[InvertedIndex, dict[str, TermStats]]:
    vocabulary, stats = fit_vocabulary((doc.content for doc in corpus.values()), config)
    postings: dict[str, dict[str, int]] = {term: {} for term in sorted(vocabulary)}
    df = {term: stats[term].df for term in postings}
    cf = {term: stats[term].cf for term in postings}
    n_docs = len(corpus)
    vsm_idf = {term: 1 + log((n_docs + 1) / (count + 1)) for term, count in df.items()}
    bm25_idf = {
        term: log1p((n_docs - count + 0.5) / (count + 0.5)) for term, count in df.items()
    }
    lengths = {}
    norms = {}
    for doc_id, doc in corpus.items():
        counts = Counter(term for term in analyze(doc.content, config) if term in vocabulary)
        lengths[doc_id] = counts.total()
        squared_norm = 0.0
        for term, tf in counts.items():
            postings[term][doc_id] = tf
            squared_norm += ((1 + log(tf)) * vsm_idf[term]) ** 2
        norms[doc_id] = sqrt(squared_norm)
    index = InvertedIndex(
        config=config,
        corpus_sha256=corpus_sha256,
        titles={doc_id: doc.title for doc_id, doc in corpus.items()},
        snippets={doc_id: doc.text[:240] for doc_id, doc in corpus.items()},
        postings=postings,
        df=df,
        cf=cf,
        doc_lengths=lengths,
        doc_norms=norms,
        vsm_idf=vsm_idf,
        bm25_idf=bm25_idf,
        n_docs=n_docs,
        avgdl=sum(lengths.values()) / n_docs if n_docs else 0.0,
    )
    return index, stats


def save_index(index: InvertedIndex, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Work on a separate file so a write failure leaves the previous index readable.
    with TemporaryDirectory(dir=path.parent) as temporary:
        staged = Path(temporary) / path.name
        # Avoid copying the large postings dictionaries.
        payload = {**vars(index), "config": asdict(index.config), "schema_version": SCHEMA_VERSION}
        with staged.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        staged.replace(path)


def load_index(path: Path) -> InvertedIndex:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if payload.pop("schema_version", None) != SCHEMA_VERSION:
        raise ValueError(f"{path}: incompatible index schema")
    payload["config"] = AnalyzerConfig(**payload["config"])
    return InvertedIndex(**payload)
