"""ARIMA 1-step forecasts with fixed order (offline TS challenger)."""

from __future__ import annotations

import logging
import warnings
from typing import Any

import numpy as np
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.arima.model import ARIMA

from ml.selection.eval import score
from ml.selection.series import SeriesForecastTask

logger = logging.getLogger(__name__)

DEFAULT_ORDER = (1, 0, 0)


def forecast_arima(
    history: list[float],
    *,
    order: tuple[int, int, int] = DEFAULT_ORDER,
) -> tuple[float, bool]:
    """1-step ARIMA forecast.

    Returns ``(prediction, used_fallback)``. Non-convergence / fit errors → last mid.
    """
    if not history:
        raise ValueError("empty history")
    last = float(history[-1])
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            warnings.simplefilter("ignore", UserWarning)
            model = ARIMA(
                np.asarray(history, dtype=float),
                order=order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            fitted = model.fit(method_kwargs={"warn_convergence": False})
        # mle_retvals may be missing on some code paths
        retvals = getattr(fitted, "mle_retvals", None) or {}
        if retvals.get("converged") is False:
            return last, True
        pred = float(fitted.forecast(1)[0])
        if not np.isfinite(pred):
            return last, True
        return pred, False
    except Exception as exc:  # noqa: BLE001 — per-series fallback is intentional
        logger.debug("ARIMA%s fit failed (%s); using last mid", order, exc)
        return last, True


def evaluate_arima(
    tasks: list[SeriesForecastTask],
    *,
    order: tuple[int, int, int] = DEFAULT_ORDER,
) -> dict[str, Any]:
    """Score ARIMA vs naive (last mid) on the same task mask."""
    y_true: list[float] = []
    y_arima: list[float] = []
    y_naive: list[float] = []
    n_fallback = 0

    for task in tasks:
        pred, fell_back = forecast_arima(task.history, order=order)
        if fell_back:
            n_fallback += 1
        y_true.append(task.y_true)
        y_arima.append(pred)
        y_naive.append(float(task.history[-1]))

    return {
        "n_tasks": len(tasks),
        "n_fallback": n_fallback,
        "order": order,
        "arima": score(y_true, y_arima),
        "naive": score(y_true, y_naive),
    }
