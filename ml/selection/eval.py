"""Shared holdout contract: load → temporal split → scores (train + selection).

``ml.train.Trainer`` publishes the champion; selection compares candidates on the
same holdout without writing ``baseline_latest``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import logging
import math

import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml.dataset_version import fingerprint
from ml.features import FEATURE_COLS, TARGET
from ml.split import temporal_split

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "processed" / "features_latest.jsonl"

logger = logging.getLogger(__name__)


class DataLoader:
    def __init__(
        self,
        input_path: Path = DEFAULT_INPUT,
        require_key: str = "zona_omi",
    ):
        self.input_path = input_path
        self.require_key = require_key

    def load(self) -> list[dict[str, Any]]:
        if not self.input_path.is_file():
            raise FileNotFoundError(f"Input not found: {self.input_path}")

        rows: list[dict[str, Any]] = []
        dropped_target = 0
        dropped_key = 0
        for line in self.input_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get(TARGET) is None:
                dropped_target += 1
                continue
            key_val = row.get(self.require_key)
            if key_val is None or key_val == "":
                dropped_key += 1
                continue
            rows.append(row)
        logger.info(
            "Loaded %s rows from %s (dropped missing target=%s, missing %s=%s)",
            len(rows),
            self.input_path,
            dropped_target,
            self.require_key,
            dropped_key,
        )
        return rows


class MetricsCalculator:
    def evaluate(self, y_true: list[float], y_pred: list[float]) -> dict[str, float]:
        mae = float(mean_absolute_error(y_true, y_pred))
        rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
        r2 = float(r2_score(y_true, y_pred)) if len(y_true) >= 2 else float("nan")
        return {"mae": round(mae, 4), "rmse": round(rmse, 4), "r2": round(r2, 4)}


@dataclass(frozen=True)
class HoldoutBundle:
    """Same temporal holdout for every selection candidate and for train metrics."""

    X_train: pd.DataFrame
    y_train: list[float]
    X_test: pd.DataFrame
    y_test: list[float]
    split_mode: str
    n_rows: int
    n_train: int
    n_test: int
    dataset: dict[str, Any]
    feature_cols: list[str]


def extract_xy(
    rows: list[dict[str, Any]],
    feature_cols: list[str] | None = None,
) -> tuple[pd.DataFrame, list[float]]:
    cols = list(FEATURE_COLS if feature_cols is None else feature_cols)
    X = pd.DataFrame([{c: r.get(c) for c in cols} for r in rows])
    y = [float(r[TARGET]) for r in rows]
    return X, y


def score(y_true: list[float], y_pred: list[float]) -> dict[str, float]:
    return MetricsCalculator().evaluate(y_true, y_pred)


def naive_scores(X_test: pd.DataFrame, y_test: list[float]) -> dict[str, float]:
    """Lag-1 baseline on rows with non-null ``loc_mid_lag``."""
    mask = X_test["loc_mid_lag"].notna()
    y_true = [y for y, ok in zip(y_test, mask) if ok]
    y_lag = X_test.loc[mask, "loc_mid_lag"].tolist()
    raw = score(y_true, y_lag)
    return {f"{k}_naive": v for k, v in raw.items()}


def prepare_holdout(
    data_path: Path,
    feature_cols: list[str] | None = None,
) -> HoldoutBundle:
    cols = list(FEATURE_COLS if feature_cols is None else feature_cols)
    rows = DataLoader(data_path).load()
    train_rows, test_rows, split_mode = temporal_split(rows)
    if not train_rows or not test_rows:
        raise ValueError(
            f"Split produced empty set (train={len(train_rows)}, test={len(test_rows)})"
        )
    X_train, y_train = extract_xy(train_rows, cols)
    X_test, y_test = extract_xy(test_rows, cols)
    return HoldoutBundle(
        X_train=X_train,
        y_train=y_train,
        X_test=X_test,
        y_test=y_test,
        split_mode=split_mode,
        n_rows=len(rows),
        n_train=len(train_rows),
        n_test=len(test_rows),
        dataset=fingerprint(data_path),
        feature_cols=cols,
    )
