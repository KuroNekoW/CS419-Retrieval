"""Generate reproducible spelling errors on the original query strings."""

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Set
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from random import Random
from string import ascii_lowercase
from tempfile import TemporaryDirectory
from unicodedata import category

OPERATIONS = ("deletion", "insertion", "substitution", "transposition")
NOISE_TYPES = (*OPERATIONS, "mixed")
_WORD_RUN = re.compile(r"\w+")
_ASCII_WORD = re.compile(r"[A-Za-z]{3,}")


@dataclass(frozen=True)
class NoiseCondition:
    noise_type: str
    seed: int
    target_rate: float | None = None
    target_k: int | None = None

    def __post_init__(self) -> None:
        if self.noise_type not in NOISE_TYPES:
            raise ValueError(f"unknown noise type {self.noise_type!r}")
        if (self.target_rate is None) == (self.target_k is None):
            raise ValueError("provide exactly one of target_rate and target_k")
        if self.target_rate is not None and not 0 <= self.target_rate <= 1:
            raise ValueError("target_rate must be between 0 and 1")
        if self.target_k is not None and self.target_k not in (1, 2):
            raise ValueError("target_k must be 1 or 2")

    @property
    def label(self) -> str:
        if self.target_rate is None:
            amount = f"k{self.target_k}"
        else:
            rate = Decimal(str(self.target_rate)).normalize() if self.target_rate else Decimal(0)
            amount = f"rate{rate:f}"
        return f"{self.noise_type}-{amount}-seed{self.seed}"


def _swaps(word: str) -> list[int]:
    # Case-only differences disappear in the retrieval analyzer.
    lower = word.lower()
    return [position for position in range(len(word) - 1) if lower[position] != lower[position + 1]]


def _edit(word: str, operation: str, rng: Random) -> tuple[str, int]:
    if operation == "insertion":
        pos = rng.randrange(len(word) + 1)
        letter = rng.choice(ascii_lowercase)
        if word.isupper() or (pos == 0 and word[0].isupper()):
            letter = letter.upper()
        suffix = word[pos:]
        if pos == 0 and word.istitle():
            suffix = suffix[0].lower() + suffix[1:]
        return word[:pos] + letter + suffix, pos
    if operation == "transposition":
        pos = rng.choice(_swaps(word))
        first, second = word[pos : pos + 2]
        if word.istitle() and pos == 0:
            first, second = first.lower(), second.upper()
        return word[:pos] + second + first + word[pos + 2 :], pos
    pos = rng.randrange(len(word))
    if operation == "deletion":
        suffix = word[pos + 1 :]
        if pos == 0 and word.istitle():
            suffix = suffix[0].upper() + suffix[1:]
        return word[:pos] + suffix, pos
    letter = rng.choice(ascii_lowercase.replace(word[pos].lower(), ""))
    if word[pos].isupper():
        letter = letter.upper()
    return word[:pos] + letter + word[pos + 1 :], pos


def _eligible_tokens(original: str, noise_type: str) -> list[tuple[int, re.Match[str]]]:
    return [
        (token_index, match)
        for token_index, match in enumerate(_WORD_RUN.finditer(original))
        if _ASCII_WORD.fullmatch(match.group())
        and not (match.start() and category(original[match.start() - 1]).startswith("M"))
        and not (match.end() < len(original) and category(original[match.end()]).startswith("M"))
        and (noise_type != "transposition" or _swaps(match.group()))
    ]


def eligible_token_count(original: str, noise_type: str = "mixed") -> int:
    """Count candidates using the same policy as the noise generator."""
    return len(_eligible_tokens(original, noise_type))


def generate_noise(
    qid: str,
    original: str,
    split: str,
    condition: NoiseCondition,
    *,
    vocabulary: Set[str] | None = None,
) -> dict:
    """Return one traceable variant with zero-based token and character positions."""
    variant_id = f"{split}/{condition.label}/{qid}"
    rng = Random(int.from_bytes(hashlib.sha256(variant_id.encode("utf-8")).digest()))
    eligible = _eligible_tokens(original, condition.noise_type)
    count = len(eligible)
    if condition.target_rate is not None:
        amount = Decimal(str(condition.target_rate)) * count
        requested = int(amount.to_integral_value(rounding=ROUND_HALF_UP))
    else:
        requested = condition.target_k
    if condition.target_k is not None and requested > count:
        status = "insufficient_eligible"
        selected = []
    elif not count:
        status = "no_eligible"
        selected = []
    else:
        status = "edited" if requested else "unchanged"
        selected = sorted(rng.sample(eligible, requested), key=lambda entry: entry[0])

    chunks = []
    edits = []
    end = 0
    for token_index, match in selected:
        word = match.group()
        operation = condition.noise_type
        if operation == "mixed":
            operation = rng.choice(OPERATIONS if _swaps(word) else OPERATIONS[:-1])
        new_word, position = _edit(word, operation, rng)
        chunks.extend((original[end : match.start()], new_word))
        end = match.end()
        edits.append({
            "token_index": token_index,
            "original_token": word,
            "modified_token": new_word,
            "operation": operation,
            "character_position": position,
            "matches_corpus_word": None if vocabulary is None else new_word.lower() in vocabulary,
        })
    chunks.append(original[end:])
    return {
        "qid": qid,
        "variant_id": variant_id,
        "split": split,
        "original": original,
        "noisy": "".join(chunks),
        **asdict(condition),
        "eligible_count": count,
        "edited_count": len(edits),
        "actual_rate": len(edits) / count if count else 0.0,
        "edits": edits,
        "status": status,
    }


def write_noise_run(
    output: Path,
    queries: Mapping[str, str],
    split: str,
    condition: NoiseCondition,
    *,
    vocabulary: Set[str] | None = None,
) -> dict:
    if output.exists():
        raise FileExistsError(f"{output} already exists; choose a new output location")
    output.parent.mkdir(parents=True, exist_ok=True)
    records = [
        generate_noise(qid, queries[qid], split, condition, vocabulary=vocabulary)
        for qid in sorted(queries)
    ]
    eligible = sum(record["eligible_count"] for record in records)
    edited = sum(record["edited_count"] for record in records)
    encoded = "".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in records
    ).encode("utf-8")
    manifest = {
        "schema_version": 1,
        "split": split,
        **asdict(condition),
        "query_count": len(records),
        "changed_query_count": sum(record["original"] != record["noisy"] for record in records),
        "eligible_token_count": eligible,
        "edited_token_count": edited,
        "actual_rate": edited / eligible if eligible else 0.0,
        "edited_count_distribution": dict(sorted(Counter(record["edited_count"] for record in records).items())),
        "status_counts": dict(sorted(Counter(record["status"] for record in records).items())),
        "edits_matching_corpus_word": (
            None if vocabulary is None else
            sum(edit["matches_corpus_word"] for record in records for edit in record["edits"])
        ),
        "noisy_queries_sha256": hashlib.sha256(encoded).hexdigest(),
    }
    with TemporaryDirectory(dir=output.parent) as staging:
        staged = Path(staging) / "noise"
        staged.mkdir()
        (staged / "noisy_queries.jsonl").write_bytes(encoded)
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        staged.rename(output)
    return manifest
