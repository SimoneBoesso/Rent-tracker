"""Unit tests for selection holdout contract (Fase 0)."""

from __future__ import annotations

import json
from pathlib import Path

from ml.selection.eval import naive_scores, prepare_holdout, score
from tests.omi_rows import omi_feature_row


def _write_features(path: Path, n: int = 24) -> None:
    rows = [
        omi_feature_row(i, day="2026-03-01" if i < 12 else "2026-09-08", loc_mid_lag=12.0 + i)
        for i in range(n)
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_prepare_holdout_same_fingerprint(tmp_path: Path):
    inp = tmp_path / "features.jsonl"
    _write_features(inp)
    a = prepare_holdout(inp)
    b = prepare_holdout(inp)
    assert a.split_mode == "temporal_last_semester"
    assert a.n_train + a.n_test == a.n_rows == 24
    assert a.n_test == 12
    assert a.dataset["sha256"] == b.dataset["sha256"]
    assert list(a.X_test.columns) == a.feature_cols


def test_naive_and_score_helpers(tmp_path: Path):
    inp = tmp_path / "features.jsonl"
    _write_features(inp)
    holdout = prepare_holdout(inp)
    naive = naive_scores(holdout.X_test, holdout.y_test)
    assert "mae_naive" in naive and "rmse_naive" in naive and "r2_naive" in naive
    # Perfect predictions → zero MAE
    assert score(holdout.y_test, holdout.y_test)["mae"] == 0.0
