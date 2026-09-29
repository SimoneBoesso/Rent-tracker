"""Unit tests for series view over panel features (Fase 3 / opzione C)."""

from __future__ import annotations

from etl.semester import semester_key
from ml.features import TARGET
from ml.selection.series import build_series_by_key, iter_forecast_tasks


def _row(key: tuple[str, str, str], semester: str, mid: float) -> dict:
    return {
        "zona_omi": key[0],
        "tipologia": key[1],
        "stato": key[2],
        "semester": semester,
        TARGET: mid,
    }


def test_build_series_by_key_sorted_three_semesters():
    key = ("B12", "Abitazioni civili", "OTTIMO")
    # Deliberately out of chronological order in the input list
    rows = [
        _row(key, "2025-1", 23.0),
        _row(key, "2024-1", 21.0),
        _row(key, "2024-2", 22.0),
    ]

    by_key = build_series_by_key(rows)

    assert list(by_key.keys()) == [key]
    series = by_key[key]
    assert len(series) == 3
    assert [sem for sem, _ in series] == [
        semester_key("2024-1"),
        semester_key("2024-2"),
        semester_key("2025-1"),
    ]
    assert [mid for _, mid in series] == [21.0, 22.0, 23.0]


def test_build_series_drops_ambiguous_same_semester():
    key = ("B1", "Abitazioni civili", "NORMALE")
    rows = [
        _row(key, "2024-1", 10.0),
        _row(key, "2024-2", 11.0),
        _row(key, "2025-1", 12.0),
        _row(key, "2025-1", 99.0),  # collision
    ]
    by_key = build_series_by_key(rows)
    assert key not in by_key


def test_iter_forecast_tasks_min_len_and_key_join():
    key_ok = ("B12", "Abitazioni civili", "OTTIMO")
    key_short = ("C14", "Abitazioni civili", "NORMALE")

    train_rows = [
        _row(key_ok, "2024-1", 21.0),
        _row(key_ok, "2024-2", 22.0),
        _row(key_short, "2024-2", 10.0),  # only 1 train point → skip if min_len=2
    ]
    test_rows = [
        _row(key_ok, "2025-1", 23.0),
        _row(key_short, "2025-1", 11.0),
    ]

    tasks = iter_forecast_tasks(train_rows, test_rows, min_len=2)

    assert len(tasks) == 1
    assert tasks[0].key == key_ok
    assert tasks[0].history == [21.0, 22.0]
    assert tasks[0].y_true == 23.0
