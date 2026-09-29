"""Offline ARIMA challenger (Fase 4) — series view on features_latest."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import mlflow

from ml.dataset_version import fingerprint
from ml.selection.arima import DEFAULT_ORDER, evaluate_arima
from ml.selection.eval import DEFAULT_INPUT, DataLoader
from ml.selection.series import DEFAULT_MIN_LEN, iter_forecast_tasks
from ml.split import temporal_split

DEFAULT_EXPERIMENT = "roma-rent-arima-optimization"


def _parse_order(text: str) -> tuple[int, int, int]:
    parts = [int(x.strip()) for x in text.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("order must be p,d,q (e.g. 1,0,0)")
    return parts[0], parts[1], parts[2]


def run_arima_selection(
    *,
    input_path=DEFAULT_INPUT,
    min_len: int = DEFAULT_MIN_LEN,
    order: tuple[int, int, int] = DEFAULT_ORDER,
    notes: str | None = None,
) -> dict:
    rows = DataLoader(input_path).load()
    train_rows, test_rows, split_mode = temporal_split(rows)
    tasks = iter_forecast_tasks(train_rows, test_rows, min_len=min_len)
    dataset = fingerprint(input_path)
    result = evaluate_arima(tasks, order=order)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    order_label = f"arima_{order[0]}{order[1]}{order[2]}"
    with mlflow.start_run(run_name=f"arima-{stamp}"):
        mlflow.set_tag("role", "parent")
        mlflow.set_tag("model", "ARIMA")
        if notes:
            mlflow.set_tag("notes", notes)
            mlflow.log_param("notes", notes)
        mlflow.log_param("dataset_sha256", dataset["sha256"])
        mlflow.log_param("split_mode", split_mode)
        mlflow.log_param("min_len", min_len)
        mlflow.log_param("n_train_rows", len(train_rows))
        mlflow.log_param("n_test_rows", len(test_rows))
        mlflow.log_param("n_tasks", result["n_tasks"])
        mlflow.log_param("n_fallback", result["n_fallback"])
        mlflow.log_param("order", str(order))
        for k, v in result["arima"].items():
            mlflow.log_metric(f"arima_{k}", v)
        for k, v in result["naive"].items():
            mlflow.log_metric(f"naive_{k}", v)

        with mlflow.start_run(run_name=order_label, nested=True):
            mlflow.set_tag("role", "child")
            mlflow.set_tag("model", "ARIMA")
            mlflow.log_param("order_p", order[0])
            mlflow.log_param("order_d", order[1])
            mlflow.log_param("order_q", order[2])
            mlflow.log_param("n_fallback", result["n_fallback"])
            for k, v in result["arima"].items():
                mlflow.log_metric(k, v)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline ARIMA selection (series view).")
    parser.add_argument("--tracking-uri", type=str, default="http://127.0.0.1:5000")
    parser.add_argument("--experiment-name", type=str, default=DEFAULT_EXPERIMENT)
    parser.add_argument("--notes", type=str, default=None)
    parser.add_argument("--min-len", type=int, default=DEFAULT_MIN_LEN)
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT))
    parser.add_argument(
        "--order",
        type=_parse_order,
        default=DEFAULT_ORDER,
        help="Fixed ARIMA order p,d,q (default 1,0,0)",
    )
    args = parser.parse_args()

    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment(args.experiment_name)

    result = run_arima_selection(
        input_path=Path(args.input),
        min_len=args.min_len,
        order=args.order,
        notes=args.notes,
    )
    print(
        f"n_tasks={result['n_tasks']} n_fallback={result['n_fallback']} "
        f"order={result['order']} "
        f"arima_mae={result['arima']['mae']} naive_mae={result['naive']['mae']}"
    )


if __name__ == "__main__":
    main()
