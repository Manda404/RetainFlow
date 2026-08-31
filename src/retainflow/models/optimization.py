"""Small optimization helpers for the first CatBoost iteration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatBoostSearchSpace:
    iterations: tuple[int, ...] = (200, 300, 500)
    learning_rate: tuple[float, ...] = (0.03, 0.05, 0.08)
    depth: tuple[int, ...] = (4, 6, 8)


def default_search_space() -> CatBoostSearchSpace:
    return CatBoostSearchSpace()
