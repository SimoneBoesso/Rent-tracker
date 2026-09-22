from geopandas import read_file
from pathlib import Path

from etl.extract.coordinates_loader import CoordinatesLoader, find_zone_by_coordinates

MONTEVERDE = (41.88035921281237, 12.463022292883036)
MILANO = (45.47377982581601, 9.185625951427367)


def test_omi_boundaries(tmp_path: Path):
    gdf = CoordinatesLoader("data/raw/omi/boundaries/H501.kml").load(tmp_path / "H501.geojson")
    assert find_zone_by_coordinates(gdf, *MONTEVERDE) == "C12"
    assert find_zone_by_coordinates(gdf, *MILANO) is None


def test_find_zone_by_coordinates(tmp_path: Path):
    CoordinatesLoader("data/raw/omi/boundaries/H501.kml").load(tmp_path / "H501.geojson")
    gdf = read_file(tmp_path / "H501.geojson")
    assert find_zone_by_coordinates(gdf, *MONTEVERDE) == "C12"
    assert find_zone_by_coordinates(gdf, *MILANO) is None
