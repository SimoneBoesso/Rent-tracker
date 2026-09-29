"""Offline SES challenger (Fase 4 slice A) — series view on features_latest."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import mlflow

from ml.dataset_version import fingerprint
from ml.selection.eval import DEFAULT_INPUT, DataLoader
from ml.selection.series import DEFAULT_MIN_LEN, iter_forecast_tasks
from ml.selection.ses import evaluate_ses
from ml.split import temporal_split

DEFAULT_EXPERIMENT = "roma-rent-ses-optimization"


def run_ses_selection(
    *,
    input_path=DEFAULT_INPUT,
    min_len: int = DEFAULT_MIN_LEN,
    notes: str | None = None,
) -> dict:
    rows = DataLoader(input_path).load()
    train_rows, test_rows, split_mode = temporal_split(rows)
    tasks = iter_forecast_tasks(train_rows, test_rows, min_len=min_len)
    dataset = fingerprint(input_path)
    result = evaluate_ses(tasks)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with mlflow.start_run(run_name=f"ses-{stamp}"):
        mlflow.set_tag("role", "parent")
        mlflow.set_tag("model", "SES")
        if notes:
            mlflow.set_tag("notes", notes)
            mlflow.log_param("notes", notes)
        mlflow.log_param("dataset_sha256", dataset["sha256"])
        mlflow.log_param("split_mode", split_mode)
        mlflow.log_param("min_len", min_len)
        mlflow.log_param("n_train_rows", len(train_rows))
        mlflow.log_param("n_test_rows", len(test_rows))
        mlflow.log_param("n_tasks", result["n_tasks"])
        for k, v in result["ses"].items():
            mlflow.log_metric(f"ses_{k}", v)
        for k, v in result["naive"].items():
            mlflow.log_metric(f"naive_{k}", v)

        with mlflow.start_run(run_name="ses_default", nested=True):
            mlflow.set_tag("role", "child")
            mlflow.set_tag("model", "SES")
            mlflow.log_param("method", "SimpleExpSmoothing")
            mlflow.log_param("optimized", True)
            for k, v in result["ses"].items():
                mlflow.log_metric(k, v)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline SES selection (series view).")
    parser.add_argument("--tracking-uri", type=str, default="http://127.0.0.1:5000")
    parser.add_argument("--experiment-name", type=str, default=DEFAULT_EXPERIMENT)
    parser.add_argument("--notes", type=str, default=None)
    parser.add_argument("--min-len", type=int, default=DEFAULT_MIN_LEN)
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT))
    args = parser.parse_args()

    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment(args.experiment_name)

    result = run_ses_selection(
        input_path=Path(args.input),
        min_len=args.min_len,
        notes=args.notes,
    )
    print(
        f"n_tasks={result['n_tasks']} "
        f"ses_mae={result['ses']['mae']} naive_mae={result['naive']['mae']}"
    )


if __name__ == "__main__":
    main()
