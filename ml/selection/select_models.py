"""Offline model selection with MLflow nested runs (parent = search, child = config)."""

from __future__ import annotations

from datetime import datetime, timezone

import mlflow
import pandas as pd

from ml.pipelines import make_serving_pipeline
from ml.pipelines.config import CandidateConfig, default_candidates, grid_search_candidates
from ml.selection.eval import (
    DEFAULT_INPUT,
    HoldoutBundle,
    naive_scores,
    prepare_holdout,
    score,
)


def train_and_evaluate_model(
    cfg: CandidateConfig,
    holdout: HoldoutBundle,
    X_train: pd.DataFrame,
    y_train: list[float],
    X_test: pd.DataFrame,
    y_test: list[float],
) -> dict[str, float]:
    """Fit one candidate and log a *nested* MLflow run under the active parent."""
    model_name = cfg.candidate

    if cfg.candidate == "naive":
        model = cfg.factory.make()
    else:
        model = make_serving_pipeline(cfg.factory)

    with mlflow.start_run(run_name=model_name, nested=True):
        mlflow.set_tag("model", model_name)
        mlflow.set_tag("role", "child")
        mlflow.log_param("dataset_sha256", holdout.dataset["sha256"])
        mlflow.log_params(cfg.params)

        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        if cfg.candidate == "naive":
            raw = naive_scores(X_test, y_test)
            metrics = {
                "mae": raw["mae_naive"],
                "rmse": raw["rmse_naive"],
                "r2": raw["r2_naive"],
            }
        else:
            metrics = score(y_test, y_pred)

        for key, value in metrics.items():
            mlflow.log_metric(key, value)

        return metrics


def select_models(
    configs: list[CandidateConfig],
    holdout: HoldoutBundle,
) -> CandidateConfig | None:
    """Run all configs as nested children; parent holds search metadata + best_*."""
    X_train, y_train = holdout.X_train, holdout.y_train
    X_test, y_test = holdout.X_test, holdout.y_test

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parent_name = f"selection-{stamp}"

    best_metrics: dict[str, float] | None = None
    best_cfg: CandidateConfig | None = None

    with mlflow.start_run(run_name=parent_name):
        mlflow.set_tag("role", "parent")
        mlflow.log_param("dataset_sha256", holdout.dataset["sha256"])
        mlflow.log_param("split_mode", holdout.split_mode)
        mlflow.log_param("n_train", holdout.n_train)
        mlflow.log_param("n_test", holdout.n_test)
        mlflow.log_param("n_candidates", len(configs))

        for cfg in configs:
            metrics = train_and_evaluate_model(
                cfg, holdout, X_train, y_train, X_test, y_test
            )
            if best_metrics is None or metrics["mae"] < best_metrics["mae"]:
                best_metrics = metrics
                best_cfg = cfg

        if best_cfg is not None and best_metrics is not None:
            mlflow.set_tag("best_candidate", best_cfg.candidate)
            mlflow.log_metrics({f"best_{k}": v for k, v in best_metrics.items()})

    return best_cfg


def main() -> None:
    mlflow.set_tracking_uri("http://127.0.0.1:5000")
    mlflow.set_experiment("roma-rent-selection")

    holdout = prepare_holdout(DEFAULT_INPUT)
    best = select_models(grid_search_candidates(), holdout)
    print(best)


if __name__ == "__main__":
    main()
