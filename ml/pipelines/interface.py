"""Regressor factory contract for plug-in models in the OMI pipeline."""

from __future__ import annotations

from typing import Protocol

from sklearn.base import BaseEstimator
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge


class RegressorFactory(Protocol):
    def make(self, cat_idx: list[int]) -> BaseEstimator: ...


class HistGradientBoostingFactory:
    """Default baseline: HGB on ordinal-encoded cats (no native categorical_features).

    Native HGB categoricals break TreeSHAP additivity (shap 0.52 / sklearn 1.9);
    OrdinalEncoder + numeric splits keeps RF-10d explanations reconstructible.
    ``cat_idx`` is accepted for RegressorFactory compatibility and ignored.
    """

    def make(self, cat_idx: list[int]) -> BaseEstimator:
        return HistGradientBoostingRegressor(random_state=42)


class RidgeFactory:
    """Simple linear baseline; ignores cat_idx (cats already ordinal-encoded)."""

    def make(self, cat_idx: list[int]) -> BaseEstimator:
        return Ridge()


class LinearRegressionFactory:
    """OLS linear regression; ignores cat_idx (cats already ordinal-encoded)."""

    def make(self, cat_idx: list[int]) -> BaseEstimator:
        return LinearRegression()
