"""Train a baseline regressor for €/m²/month (RF-05) with MLflow tracking (RF-11 lite)."""

from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import logging
import math

import joblib
import mlflow
import pandas as pd
from sklearn.pipeline import Pipeline

from ml.dataset_version import write_dataset_json
from ml.features import (
    CATEGORICAL_FEATURES,
    FEATURE_COLS,
    NUMERIC_FEATURES,
    TARGET,
)
from ml.pipelines import make_serving_pipeline
from ml.selection.eval import (
    DEFAULT_INPUT,
    DataLoader,
    MetricsCalculator,
    extract_xy,
    naive_scores,
    prepare_holdout,
)
from ml.split import temporal_split as split_by_semester

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
MLFLOW_DB = Path(__file__).resolve().parents[1] / "mlflow.db"
DEFAULT_TRACKING_URI = f"sqlite:///{MLFLOW_DB.resolve()}"

# Re-export for callers that still import columns / loader from ml.train
__all__ = [
    "CATEGORICAL_FEATURES",
    "DEFAULT_INPUT",
    "DEFAULT_TRACKING_URI",
    "DataLoader",
    "FEATURE_COLS",
    "MODELS_DIR",
    "MetricsCalculator",
    "NUMERIC_FEATURES",
    "TARGET",
    "Trainer",
    "train",
]

logger = logging.getLogger(__name__)


class Trainer:
    def __init__(
        self,
        pipeline: Pipeline,
        metrics_calculator: MetricsCalculator,
        data_loader: DataLoader,
        feature_cols: list[str] | None = None,
    ):
        self.pipeline: Pipeline = pipeline
        self.metrics_calculator: MetricsCalculator = metrics_calculator
        self.data_loader: DataLoader = data_loader
        self.feature_cols = feature_cols or list(FEATURE_COLS)
        self.metrics: dict[str, Any] = {}
        self.split_mode: str = ""
        self.n_rows: int = 0
        self.n_train: int = 0
        self.n_test: int = 0

    def split_data(
        self,
    ) -> tuple[pd.DataFrame, list[float], pd.DataFrame, list[float]]:
        holdout = prepare_holdout(self.data_loader.input_path, self.feature_cols)
        self.split_mode = holdout.split_mode
        self.n_rows = holdout.n_rows
        self.n_train = holdout.n_train
        self.n_test = holdout.n_test
        return holdout.X_train, holdout.y_train, holdout.X_test, holdout.y_test

    def temporal_split(
        self,
        rows: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
        """Delegate to ml.split.temporal_split (kept for tests / callers)."""
        return split_by_semester(rows)

    def extract_features_and_target(
        self, rows: list[dict[str, Any]]
    ) -> tuple[pd.DataFrame, list[float]]:
        return extract_xy(rows, self.feature_cols)

    def fit(self, X_train: pd.DataFrame, y_train: list[float]) -> Pipeline:
        self.pipeline.fit(X_train, y_train)
        return self.pipeline

    def predict(self, X_test: pd.DataFrame) -> list[float]:
        y_pred = self.pipeline.predict(X_test)
        return list(y_pred)

    def evaluate(self, y_test: list[float], y_pred: list[float]) -> dict[str, Any]:
        scores = self.metrics_calculator.evaluate(y_test, y_pred)
        self.metrics = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input": str(self.data_loader.input_path),
            "model": type(self.pipeline.named_steps["model"]).__name__,
            "features": self.feature_cols,
            "target": TARGET,
            "split_mode": self.split_mode,
            "n_rows": self.n_rows,
            "n_train": self.n_train,
            "n_test": self.n_test,
            **scores,
        }
        return self.metrics

    def save_model(self, model_path: Path) -> None:
        joblib.dump(self.pipeline, model_path)

    def save_metrics(self, metrics_path: Path) -> None:
        metrics_path.write_text(
            json.dumps(self.metrics, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def run(
        self,
        models_dir: Path = MODELS_DIR,
        tracking_uri: str | None = DEFAULT_TRACKING_URI,
    ) -> Path:
        """Holdout eval on last semester, then refit on all rows for the saved artifact."""
        holdout = prepare_holdout(self.data_loader.input_path, self.feature_cols)
        self.split_mode = holdout.split_mode
        self.n_rows = holdout.n_rows
        self.n_train = holdout.n_train
        self.n_test = holdout.n_test

        X_train, y_train = holdout.X_train, holdout.y_train
        X_test, y_test = holdout.X_test, holdout.y_test

        self.fit(X_train, y_train)
        y_pred = self.predict(X_test)

        lag_naive = naive_scores(X_test, y_test)
        metrics = self.evaluate(y_test, y_pred)
        metrics.update(lag_naive)

        dataset_meta = holdout.dataset
        metrics["dataset"] = dataset_meta
        scores = {k: float(metrics[k]) for k in ("mae", "rmse", "r2")}

        # Metrics stay holdout; artifact for serve uses the full history.
        X_all = pd.concat([X_train, X_test], ignore_index=True)
        y_all = y_train + y_test
        self.fit(X_all, y_all)
        metrics["fit_mode"] = "holdout_then_refit_full"
        metrics["n_fit"] = len(y_all)

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = models_dir / f"baseline_{run_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        model_path = out_dir / "model.joblib"
        metrics_path = out_dir / "metrics.json"
        dataset_path = out_dir / "dataset.json"

        self.save_model(model_path)
        self.save_metrics(metrics_path)
        write_dataset_json(dataset_meta, dataset_path)

        latest_dir = models_dir / "baseline_latest"
        latest_dir.mkdir(parents=True, exist_ok=True)
        self.save_model(latest_dir / "model.joblib")
        self.save_metrics(latest_dir / "metrics.json")
        write_dataset_json(dataset_meta, latest_dir / "dataset.json")

        logger.info(
            "Test MAE=%.3f RMSE=%.3f R2=%.3f Naive MAE=%.3f Naive RMSE=%.3f Naive R2=%.3f (split=%s, n_train=%s, n_test=%s, dataset_sha256=%s) → %s",
            scores["mae"],
            scores["rmse"],
            scores["r2"],
            lag_naive["mae_naive"],
            lag_naive["rmse_naive"],
            lag_naive["r2_naive"],
            self.split_mode,
            self.n_train,
            self.n_test,
            dataset_meta["sha256"][:12],
            out_dir,
        )

        if tracking_uri is not None:
            mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment("roma-rent-baseline")
            with mlflow.start_run(run_name=f"baseline_{run_id}"):
                mlflow.log_params(
                    {
                        "model": type(self.pipeline.named_steps["model"]).__name__,
                        "split_mode": self.split_mode,
                        "fit_mode": metrics["fit_mode"],
                        "n_train": self.n_train,
                        "n_test": self.n_test,
                        "n_fit": metrics["n_fit"],
                        "features": ",".join(self.feature_cols),
                        "dataset_sha256": dataset_meta["sha256"],
                    }
                )
                mlflow.log_metrics({**scores, **lag_naive})
                mlflow.log_artifact(str(model_path))
                mlflow.log_artifact(str(metrics_path))
                mlflow.log_artifact(str(dataset_path))

        return out_dir


def _numeric_cols_with_signal(rows: list[dict[str, Any]], cols: list[str]) -> list[str]:
    """Drop numeric cols with <2 distinct finite values (HGB binning would crash)."""
    keep: list[str] = []
    for col in cols:
        uniq: set[float] = set()
        for row in rows:
            val = row.get(col)
            if val is None:
                continue
            try:
                f = float(val)
            except (TypeError, ValueError):
                continue
            if math.isnan(f):
                continue
            uniq.add(f)
            if len(uniq) >= 2:
                keep.append(col)
                break
    return keep


def train(
    input_path: Path = DEFAULT_INPUT,
    models_dir: Path = MODELS_DIR,
    tracking_uri: str | None = DEFAULT_TRACKING_URI,
) -> Path:
    loader = DataLoader(input_path)
    rows = loader.load()
    # HGB needs ≥2 distinct finite values *on the train fold* (not the full dataset).
    # With 2 semesters, train is often only the earlier one → lag all-null.
    train_rows, _test_rows, _mode = split_by_semester(rows)
    numeric = _numeric_cols_with_signal(train_rows, list(NUMERIC_FEATURES))
    dropped = [c for c in NUMERIC_FEATURES if c not in numeric]
    if dropped:
        logger.warning(
            "Dropping numeric features without signal on train fold: %s "
            "(need ≥3 OMI semesters for loc_mid_lag on temporal train)",
            dropped,
        )

    feature_cols = list(numeric) + list(CATEGORICAL_FEATURES)
    trainer = Trainer(
        pipeline=make_serving_pipeline(
            numeric_features=list(numeric),
            categorical_features=list(CATEGORICAL_FEATURES),
        ),
        metrics_calculator=MetricsCalculator(),
        data_loader=loader,
        feature_cols=feature_cols,
    )
    return trainer.run(models_dir=models_dir, tracking_uri=tracking_uri)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train baseline rent €/m² model (RF-05).")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR)
    parser.add_argument("--no-mlflow", action="store_true", help="Skip local MLflow logging")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    train(
        input_path=args.input,
        models_dir=args.models_dir,
        tracking_uri=None if args.no_mlflow else DEFAULT_TRACKING_URI,
    )


if __name__ == "__main__":
    main()
