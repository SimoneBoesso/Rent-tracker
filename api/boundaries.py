from etl.extract.coordinates_loader import CoordinatesLoader, find_zone_by_coordinates
from pathlib import Path
from geopandas import read_file


def resolve_zona(lat: float, lon: float, destination_path: Path|None = None) -> str | None:

    if destination_path is None:
        destination_path = Path("data/processed/omi/boundaries/H501.geojson")
    if not destination_path.exists():
        gdf = CoordinatesLoader("data/raw/omi/boundaries/H501.kml").load(str(destination_path))
    
    else:
        gdf = read_file(destination_path)
    return find_zone_by_coordinates(gdf, lat, lon)