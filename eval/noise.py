"""Query-noise functions: the Semester-6 noise protocol, applied to queries.

Same three corruption families and the same definitions as Section 4.5 of the
Sem-6 report, so results are directly comparable in kind:

  char     for a fraction rho of words longer than 2 characters, randomly swap
           two adjacent letters, delete one letter, or insert one ASCII letter
  dropout  drop each word independently with probability rho
  oov      replace each word independently, with probability rho, by a
           synthetic token zxq<3 digits>

All functions are deterministic given the `rng`.
"""
from __future__ import annotations

import random
import string
from typing import Callable, Dict, List

INTENSITIES = (0.05, 0.10, 0.20, 0.30, 0.40, 0.50)


def _edit_word(word: str, rng: random.Random) -> str:
    op = rng.choice(("swap", "delete", "insert"))
    if op == "swap" and len(word) >= 2:
        i = rng.randrange(len(word) - 1)
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]
    if op == "delete":
        i = rng.randrange(len(word))
        return word[:i] + word[i + 1:]
    i = rng.randrange(len(word) + 1)
    return word[:i] + rng.choice(string.ascii_lowercase) + word[i:]


def char_noise(text: str, rho: float, rng: random.Random) -> str:
    words = text.split()
    eligible = [i for i, w in enumerate(words) if len(w) > 2]
    if not eligible or rho <= 0:
        return text
    n = min(len(eligible), max(0, round(rho * len(eligible))))
    # Probabilistic rounding so short queries are still perturbed at low rho.
    if n == 0 and rng.random() < rho * len(eligible):
        n = 1
    for i in rng.sample(eligible, n):
        words[i] = _edit_word(words[i], rng)
    return " ".join(words)


def word_dropout(text: str, rho: float, rng: random.Random) -> str:
    words = text.split()
    if not words or rho <= 0:
        return text
    kept = [w for w in words if rng.random() >= rho]
    if not kept:  # never emit an empty query
        kept = [rng.choice(words)]
    return " ".join(kept)


def oov_injection(text: str, rho: float, rng: random.Random) -> str:
    words = text.split()
    if rho <= 0:
        return text
    return " ".join(
        f"zxq{rng.randrange(1000):03d}" if rng.random() < rho else w for w in words
    )


NOISE_FUNCS: Dict[str, Callable[[str, float, random.Random], str]] = {
    "char": char_noise,
    "dropout": word_dropout,
    "oov": oov_injection,
}


def corrupt_queries(queries: List[str], kind: str, rho: float, seed: int) -> List[str]:
    """Corrupt every query with an independent, reproducible RNG stream."""
    fn = NOISE_FUNCS[kind]
    return [fn(q, rho, random.Random(f"{seed}-{kind}-{rho}-{i}")) for i, q in enumerate(queries)]
