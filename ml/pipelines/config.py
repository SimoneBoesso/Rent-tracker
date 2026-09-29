"""Candidate specs for offline model selection (Fase 1).

Keep hyperparams on the *regressor factory*, not on preprocessing.
``params`` are logged to MLflow; extend later for real search grids.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any

from ml.pipelines.interface import (
    RegressorFactory,
    hgb_factory,
    lr_factory,
    naive_factory,
    ridge_factory,
)

# CLI / grid filter: families we actually ship factories for.
ARCHITECTURES = ("hgb", "ridge", "lr", "linear")


@dataclass(frozen=True)
class CandidateConfig:
    """One selection candidate: id + factory (+ optional MLflow params)."""

    candidate: str
    factory: RegressorFactory
    params: dict[str, Any] = field(default_factory=dict)


def default_candidates() -> list[CandidateConfig]:
    """Small fixed set (baseline families)."""
    return [
        CandidateConfig(
            candidate="naive",
            factory=naive_factory(),
            params={"model": "Naive"},
        ),
        CandidateConfig(
            candidate="hgb",
            factory=hgb_factory(),
            params={"model": "HistGradientBoostingRegressor", "random_state": 42},
        ),
        CandidateConfig(
            candidate="ridge",
            factory=ridge_factory(),
            params={"model": "Ridge", "random_state": 42},
        ),
        CandidateConfig(
            candidate="lr",
            factory=lr_factory(),
            params={"model": "LinearRegression"},
        ),
    ]


def _hgb_grid() -> list[CandidateConfig]:
    out: list[CandidateConfig] = []
    for learning_rate, max_depth, max_iter in product(
        (0.01, 0.05, 0.1),
        (3, 5, 7),
        (100, 200),
    ):
        kw = {
            "learning_rate": learning_rate,
            "max_depth": max_depth,
            "max_iter": max_iter,
            "random_state": 42,
        }
        out.append(
            CandidateConfig(
                candidate=f"hgb_lr{learning_rate}_d{max_depth}_i{max_iter}",
                factory=hgb_factory(**kw),
                params={"model": "HistGradientBoostingRegressor", **kw},
            )
        )
    return out


def _ridge_grid() -> list[CandidateConfig]:
    out: list[CandidateConfig] = []
    for alpha in (0.01, 0.1, 1.0, 10.0, 100.0, 1000.0):
        kw = {"alpha": alpha, "random_state": 42}
        out.append(
            CandidateConfig(
                candidate=f"ridge_a{alpha}",
                factory=ridge_factory(**kw),
                params={"model": "Ridge", **kw},
            )
        )
    return out


def _lr_grid() -> list[CandidateConfig]:
    out: list[CandidateConfig] = []
    for fit_intercept in (True, False):
        kw = {"fit_intercept": fit_intercept}
        out.append(
            CandidateConfig(
                candidate=f"lr_intercept{fit_intercept}",
                factory=lr_factory(**kw),
                params={"model": "LinearRegression", **kw},
            )
        )
    return out


def grid_search_candidates(architecture: str = "hgb") -> list[CandidateConfig]:
    """Grid for one architecture family (+ naive baseline always).

    ``architecture``: ``hgb`` | ``ridge`` | ``lr`` | ``linear`` (``linear`` = Ridge + LR).
    """
    arch = architecture.strip().lower()
    if arch not in ARCHITECTURES:
        raise ValueError(
            f"Unknown architecture={architecture!r}; choose one of {ARCHITECTURES}"
        )

    out: list[CandidateConfig] = [
        CandidateConfig(
            candidate="naive",
            factory=naive_factory(),
            params={"model": "Naive"},
        )
    ]

    if arch == "hgb":
        out.extend(_hgb_grid())
    if arch in ("ridge", "linear"):
        out.extend(_ridge_grid())
    if arch in ("lr", "linear"):
        out.extend(_lr_grid())

    return out


def champion_factory() -> RegressorFactory:
    """Serve / ``ml.train`` recipe (manual promote). Not the MLflow selection winner."""
    return hgb_factory(random_state=42)
