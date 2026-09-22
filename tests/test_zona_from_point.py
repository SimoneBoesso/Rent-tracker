"""Tests for GET /meta/zona-from-point (G4 / RF-04b)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
import joblib
import pandas as pd
from fastapi.testclient import TestClient
from shapely.geometry import box

from api.main import create_app
from dashboard.geocode import geocode_address
from ml.train import FEATURE_COLS, PipelineBuilder
from tests.omi_rows import omi_feature_row


def _tiny_model(tmp_path: Path) -> Path:
    rows = [omi_feature_row(i, day="2026-09-08", loc_mid_lag=15.0 + i) for i in range(24)]
    X = pd.DataFrame([{c: r.get(c) for c in FEATURE_COLS} for r in rows])
    y = [float(r["price_per_m2_monthly"]) for r in rows]
    pipe = PipelineBuilder().build()
    pipe.fit(X, y)
    path = tmp_path / "model.joblib"
    joblib.dump(pipe, path)
    return path


def _tiny_boundaries(tmp_path: Path) -> Path:
    """One square around Monteverde-ish; zona_omi=C12."""
    path = tmp_path / "H501.geojson"
    gdf = gpd.GeoDataFrame(
        {"zona_omi": ["C12"], "geometry": [box(12.46, 41.87, 12.47, 41.89)]},
        crs="EPSG:4326",
    )
    gdf.to_file(path, driver="GeoJSON")
    return path


def test_meta_zona_from_point_hit_and_miss(tmp_path: Path):
    model = _tiny_model(tmp_path)
    boundaries = _tiny_boundaries(tmp_path)
    with TestClient(create_app(model, boundaries_path=boundaries)) as client:
        hit = client.get("/meta/zona-from-point", params={"lat": 41.88, "lon": 12.465})
        assert hit.status_code == 200
        body = hit.json()
        assert body["zona_omi"] == "C12"
        assert body["lat"] == 41.88
        assert body["lon"] == 12.465

        miss = client.get("/meta/zona-from-point", params={"lat": 45.47, "lon": 9.18})
        assert miss.status_code == 200
        assert miss.json()["zona_omi"] is None


def test_meta_zona_from_point_unavailable(tmp_path: Path):
    model = _tiny_model(tmp_path)
    missing = tmp_path / "missing.geojson"
    with patch("api.main.resolve_zona", side_effect=FileNotFoundError("no boundaries")):
        with TestClient(create_app(model, boundaries_path=missing)) as client:
            resp = client.get("/meta/zona-from-point", params={"lat": 41.88, "lon": 12.465})
            assert resp.status_code == 503


def test_geocode_address_ok_and_empty():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = [{"lat": "41.88", "lon": "12.46"}]

    with patch("dashboard.geocode.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        assert geocode_address("Via Carini 45, Roma") == (41.88, 12.46)

        mock_resp.json.return_value = []
        assert geocode_address("nowhere") is None

    assert geocode_address("   ") is None
