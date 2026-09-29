"""Unit tests for SES 1-step challenger."""

from __future__ import annotations

from ml.selection.series import SeriesForecastTask
from ml.selection.ses import evaluate_ses, forecast_ses


def test_forecast_ses_returns_finite():
    history = [10.0, 10.5, 11.0, 11.2, 11.5, 12.0]
    pred = forecast_ses(history)
    assert isinstance(pred, float)
    assert pred == pred  # not NaN


def test_evaluate_ses_vs_naive_same_mask():
    tasks = [
        SeriesForecastTask(key=("B12", "Abitazioni civili", "OTTIMO"), history=[21.0, 22.0], y_true=23.0),
        SeriesForecastTask(key=("C14", "Abitazioni civili", "NORMALE"), history=[10.0, 10.5], y_true=11.0),
    ]
    out = evaluate_ses(tasks)
    assert out["n_tasks"] == 2
    assert "mae" in out["ses"] and "mae" in out["naive"]
