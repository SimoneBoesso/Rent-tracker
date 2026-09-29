"""Simple Exponential Smoothing 1-step forecasts (offline TS challenger)."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from statsmodels.tsa.holtwinters import SimpleExpSmoothing

from ml.selection.eval import score
from ml.selection.series import SeriesForecastTask

logger = logging.getLogger(__name__)


def forecast_ses(history: list[float]) -> float:
    """1-step SES forecast; falls back to last observation on failure."""
    if not history:
        raise ValueError("empty history")
    try:
        model = SimpleExpSmoothing(
            np.asarray(history, dtype=float),
            initialization_method="estimated",
        )
        fitted = model.fit(optimized=True)
        return float(fitted.forecast(1)[0])
    except Exception as exc:  # noqa: BLE001 — per-series fallback is intentional
        logger.debug("SES fit failed (%s); using last mid", exc)
        return float(history[-1])


def evaluate_ses(tasks: list[SeriesForecastTask]) -> dict[str, Any]:
    """Score SES vs naive (last mid) on the same task mask."""
    y_true = [t.y_true for t in tasks]
    y_ses = [forecast_ses(t.history) for t in tasks]
    y_naive = [float(t.history[-1]) for t in tasks]
    return {
        "n_tasks": len(tasks),
        "ses": score(y_true, y_ses),
        "naive": score(y_true, y_naive),
    }
