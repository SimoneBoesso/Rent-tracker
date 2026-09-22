from geopandas import read_file
from geopandas.geodataframe import GeoDataFrame
from shapely.geometry import Point


class CoordinatesLoader:
    def __init__(self, file_path: str):
        self.raw_file_path = file_path

    def load(self, processed_file_path: str):
        gdf = read_file(self.raw_file_path)
        gdf["zona_omi"] = gdf["CODZONA"].astype(str).str.strip()
        gdf = gdf[["zona_omi", "geometry"]]
        gdf.to_file(filename=processed_file_path, driver="GeoJSON")

        return gdf


def find_zone_by_coordinates(gdf: GeoDataFrame, lat: float, lon: float) -> str | None:
    point = Point(lon, lat)
    hits = gdf[gdf.contains(point)]
    if len(hits) == 0:
        return None
    return str(hits["zona_omi"].iloc[0])
