"""Unit tests for ARIMA 1-step challenger."""

from __future__ import annotations

from ml.selection.arima import evaluate_arima, forecast_arima
from ml.selection.series import SeriesForecastTask


def test_forecast_arima_returns_finite():
    history = [10.0, 10.5, 11.0, 11.2, 11.5, 12.0, 12.1, 12.3]
    pred, fell_back = forecast_arima(history, order=(1, 0, 0))
    assert isinstance(pred, float)
    assert pred == pred  # not NaN
    assert isinstance(fell_back, bool)


def test_evaluate_arima_vs_naive_same_mask():
    tasks = [
        SeriesForecastTask(
            key=("B12", "Abitazioni civili", "OTTIMO"),
            history=[21.0, 21.5, 22.0, 22.2],
            y_true=23.0,
        ),
        SeriesForecastTask(
            key=("C14", "Abitazioni civili", "NORMALE"),
            history=[10.0, 10.2, 10.5, 10.8],
            y_true=11.0,
        ),
    ]
    out = evaluate_arima(tasks, order=(1, 0, 0))
    assert out["n_tasks"] == 2
    assert out["order"] == (1, 0, 0)
    assert "mae" in out["arima"] and "mae" in out["naive"]
