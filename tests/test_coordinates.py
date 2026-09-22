"""Unit tests for CoordinatesLoader / PIP (no real H501.kml — gitignored / absent in CI)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from geopandas import read_file
from shapely.geometry import box

from etl.extract.coordinates_loader import CoordinatesLoader, find_zone_by_coordinates

# Point inside the synthetic C12 box below
INSIDE = (41.88, 12.465)
OUTSIDE = (45.47, 9.18)


def _raw_with_codzona(tmp_path: Path) -> Path:
    """Minimal source with CODZONA (as in OMI KML ExtendedData)."""
    path = tmp_path / "raw_boundaries.geojson"
    gdf = gpd.GeoDataFrame(
        {"CODZONA": ["C12"], "geometry": [box(12.46, 41.87, 12.47, 41.89)]},
        crs="EPSG:4326",
    )
    gdf.to_file(path, driver="GeoJSON")
    return path


def test_omi_boundaries(tmp_path: Path):
    out = tmp_path / "H501.geojson"
    gdf = CoordinatesLoader(str(_raw_with_codzona(tmp_path))).load(str(out))
    assert list(gdf.columns) == ["zona_omi", "geometry"]
    assert find_zone_by_coordinates(gdf, *INSIDE) == "C12"
    assert find_zone_by_coordinates(gdf, *OUTSIDE) is None
    assert out.is_file()


def test_find_zone_by_coordinates(tmp_path: Path):
    out = tmp_path / "H501.geojson"
    CoordinatesLoader(str(_raw_with_codzona(tmp_path))).load(str(out))
    gdf = read_file(out)
    assert find_zone_by_coordinates(gdf, *INSIDE) == "C12"
    assert find_zone_by_coordinates(gdf, *OUTSIDE) is None
