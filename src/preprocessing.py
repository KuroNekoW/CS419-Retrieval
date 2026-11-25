"""Shared normalization and tokenization for English retrieval."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class AnalyzerConfig:
    kind: Literal["word", "char"] = "word"
    min_df: int = 1
    max_df_ratio: float = 1.0

    def __post_init__(self) -> None:
        if self.kind not in ("word", "char"):
            raise ValueError("kind must be word or char")
        if self.min_df < 1 or not 0 < self.max_df_ratio <= 1:
            raise ValueError("require min_df >= 1 and 0 < max_df_ratio <= 1")


def tokenize(text: str) -> list[str]:
    """Normalize with NFKC and lowercase, then extract ASCII letter/digit runs."""
    return _WORD.findall(unicodedata.normalize("NFKC", text).lower())


def analyze(text: str, config: AnalyzerConfig) -> list[str]:
    tokens = tokenize(text)
    if config.kind == "word":
        return tokens
    terms = []
    for token in tokens:
        if len(token) < 3:
            terms.append(f"short:{token}")
            continue
        for size in (3, 4, 5):
            terms.extend(token[start : start + size] for start in range(len(token) - size + 1))
    return terms
