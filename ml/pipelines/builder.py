"""Plug-in regressor only (Protocol factory). Preprocessing lives in ``preprocess``."""

from __future__ import annotations

from sklearn.base import BaseEstimator
from sklearn.pipeline import Pipeline

from ml.pipelines.interface import RegressorFactory, default_hgb_factory


class PipelineBuilder:
    """Build the estimator via ``RegressorFactory`` — no ColumnTransformer here."""

    def __init__(self, regressor_factory: RegressorFactory | None = None):
        self.regressor_factory: RegressorFactory = (
            default_hgb_factory() if regressor_factory is None else regressor_factory
        )
        self.model_name = self.regressor_factory.model_name

    def build(self) -> BaseEstimator:
        """Bare regressor (selection / unit tests that inject a model only)."""
        return self.regressor_factory.make()

    def build_pipeline(self) -> Pipeline:
        """Single-step sklearn Pipeline around the regressor (no preprocessing)."""
        return Pipeline(steps=[("model", self.build())])
