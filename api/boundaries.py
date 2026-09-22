"""Load OMI zone polygons and resolve (lat, lon) → zona_omi."""

from __future__ import annotations

from pathlib import Path

from geopandas import read_file

from etl.extract.coordinates_loader import CoordinatesLoader, find_zone_by_coordinates

_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOUNDARIES = _ROOT / "data" / "processed" / "omi" / "boundaries" / "H501.geojson"
DEFAULT_KML = _ROOT / "data" / "raw" / "omi" / "boundaries" / "H501.kml"


def resolve_zona(
    lat: float,
    lon: float,
    destination_path: Path | None = None,
) -> str | None:
    path = Path(destination_path) if destination_path is not None else DEFAULT_BOUNDARIES
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        gdf = CoordinatesLoader(str(DEFAULT_KML)).load(str(path))
    else:
        gdf = read_file(path)
    return find_zone_by_coordinates(gdf, lat, lon)
