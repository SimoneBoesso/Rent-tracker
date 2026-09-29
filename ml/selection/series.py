"""Series view over panel features (opzione C) — no second ETL."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from etl.semester import semester_key
from ml.features import TARGET

SeriesByKey = dict[tuple[Any, ...], list[tuple[tuple[int, int], float]]]

DEFAULT_MIN_LEN = 20


@dataclass(frozen=True)
class SeriesForecastTask:
    """One key: train history (mids) + single test-semester target."""

    key: tuple[Any, ...]
    history: list[float]
    y_true: float


def build_series_by_key(rows: list[dict[str, Any]]) -> SeriesByKey:
    """Group rows by (zona_omi, tipologia, stato); values sorted by semester.

    If the same key has **multiple distinct mids in one semester**, that key is
    dropped (OMI collisions / missing dimension). Identical duplicate rows are
    collapsed to one point.
    """
    # (key, semester_key) -> set of mids seen
    bucket: dict[tuple[Any, tuple[int, int]], set[float]] = defaultdict(set)
    for row in rows:
        key = (row.get("zona_omi"), row.get("tipologia"), row.get("stato"))
        sk = semester_key(row["semester"])
        bucket[(key, sk)].add(float(row[TARGET]))

    ambiguous: set[tuple[Any, ...]] = set()
    by_key: SeriesByKey = defaultdict(list)
    for (key, sk), mids in bucket.items():
        if len(mids) != 1:
            ambiguous.add(key)
            continue
        by_key[key].append((sk, next(iter(mids))))

    for key in ambiguous:
        by_key.pop(key, None)

    for series in by_key.values():
        series.sort(key=lambda x: x[0])

    return dict(by_key)


def iter_forecast_tasks(
    train_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    *,
    min_len: int = DEFAULT_MIN_LEN,
) -> list[SeriesForecastTask]:
    """Join test keys to train history; skip short or ambiguous series.

    Aligns by key (not dict order). Requires exactly one test mid per key.
    """
    train_s = build_series_by_key(train_rows)
    test_s = build_series_by_key(test_rows)

    tasks: list[SeriesForecastTask] = []
    for key, test_pts in test_s.items():
        if len(test_pts) != 1:
            # should not happen after de-ambig, but be strict
            continue
        history_pts = train_s.get(key, [])
        if len(history_pts) < min_len:
            continue
        tasks.append(
            SeriesForecastTask(
                key=key,
                history=[mid for _, mid in history_pts],
                y_true=float(test_pts[0][1]),
            )
        )
    return tasks
