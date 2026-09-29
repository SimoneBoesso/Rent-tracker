"""OMI feature preprocessing (NaN fill + ordinal cats) — separate from model factory."""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from ml.pipelines.config import champion_factory 

from ml.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES
from ml.pipelines.interface import RegressorFactory


class FillNanConstant(BaseEstimator, TransformerMixin):
    """Fill NaN with a constant; never drops columns (unlike older SimpleImputer)."""

    def __init__(self, fill_value: float = 0.0):
        self.fill_value = fill_value

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        arr = np.asarray(X, dtype=np.float64)
        return np.nan_to_num(arr, nan=self.fill_value)


def make_preprocessor(
    numeric_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
) -> ColumnTransformer:
    numeric = list(NUMERIC_FEATURES) if numeric_features is None else list(numeric_features)
    categorical = (
        list(CATEGORICAL_FEATURES)
        if categorical_features is None
        else list(categorical_features)
    )
    transformers: list[tuple] = []
    if numeric:
        transformers.append(("num", FillNanConstant(0.0), numeric))
    transformers.append(
        (
            "cat",
            OrdinalEncoder(
                handle_unknown="use_encoded_value",
                unknown_value=-1,
            ),
            categorical,
        )
    )
    return ColumnTransformer(transformers=transformers)

# this is used for both model selection and model serving
def make_serving_pipeline(
    regressor_factory: RegressorFactory | None = None,
    numeric_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
) -> Pipeline:
    """Compose preprocessor + model for train/serve (SHAP expects ``named_steps['pre']``)."""
    numeric = list(NUMERIC_FEATURES) if numeric_features is None else list(numeric_features)
    categorical = (
        list(CATEGORICAL_FEATURES)
        if categorical_features is None
        else list(categorical_features)
    )
    factory = regressor_factory if regressor_factory is not None else champion_factory() 
    return Pipeline(
        steps=[
            ("pre", make_preprocessor(numeric, categorical)),
            ("model", factory.make()),
        ]
    )
