"""Regressor factory contract — one parametric factory for sklearn estimators."""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np
from sklearn.base import BaseEstimator
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge


class LagNaiveRegressor(BaseEstimator):
    """Predict previous-semester mid (= loc_mid_lag column)."""

    def fit(self, X, y=None):
        return self

    def predict(self, X):
        # X DataFrame with loc_mid_lag *before* preprocessor
        return np.asarray(X["loc_mid_lag"], dtype=float)

class RegressorFactory(Protocol):
    model_name: str

    def make(self) -> BaseEstimator: ...


class SklearnRegressorFactory:
    """Single factory: name + estimator class + kwargs."""

    def __init__(
        self,
        model_name: str,
        estimator_cls: type[BaseEstimator],
        **kwargs: Any,
    ):
        self.model_name = model_name
        self._estimator_cls = estimator_cls
        self._kwargs = kwargs

    def make(self) -> BaseEstimator:
        return self._estimator_cls(**self._kwargs)


def default_hgb_factory() -> SklearnRegressorFactory:
    """Production default (TreeSHAP-friendly when used after ordinal preprocess)."""
    return SklearnRegressorFactory(
        "HistGradientBoosting",
        HistGradientBoostingRegressor,
        random_state=42,
    )


# Convenience constructors for selection config
def hgb_factory(**kwargs: Any) -> SklearnRegressorFactory:
    kw = {"random_state": 42, **kwargs}
    return SklearnRegressorFactory("HistGradientBoosting", HistGradientBoostingRegressor, **kw)


def ridge_factory(**kwargs: Any) -> SklearnRegressorFactory:
    kw = {"random_state": 42, **kwargs}
    return SklearnRegressorFactory("Ridge", Ridge, **kw)


def lr_factory(**kwargs: Any) -> SklearnRegressorFactory:
    return SklearnRegressorFactory("LinearRegression", LinearRegression, **kwargs)


## come faccio qui a creare la naive factory?
# deve ritornare il valore del semestre precedente
def naive_factory(**kwargs: Any) -> SklearnRegressorFactory:
    return SklearnRegressorFactory("Naive", LagNaiveRegressor, **kwargs)