from __future__ import annotations

import logging
from typing import Final

from pyproj import CRS, Transformer
from shapely.geometry import box
from shapely.ops import transform as shapely_transform

logger = logging.getLogger(__name__)

# Half-side of the 2 km × 2 km AOI in the projected (metric) CRS.
_HALF_SIDE_M: Final[float] = 1000.0


def _utm_crs_for_point(latitude: float, longitude: float) -> CRS:
    """Return the standard UTM CRS whose zone contains this WGS84 point.

    Norwegian (32V) and Svalbard (33X / 35X / 37X) exception zones are
    intentionally omitted — no supply-chain port of interest reaches 72 °N.
    """
    zone: int = int((longitude + 180) / 6) + 1
    epsg: int = 32600 + zone if latitude >= 0.0 else 32700 + zone
    logger.debug(
        "lat=%.4f lon=%.4f → UTM zone %d %s  EPSG:%d",
        latitude,
        longitude,
        zone,
        "N" if latitude >= 0.0 else "S",
        epsg,
    )
    return CRS.from_epsg(epsg)


def compute_aoi_bbox(
    latitude: float,
    longitude: float,
    half_side_m: float = 1000.0,
) -> list[float]:
    """Project a WGS84 point into its local UTM zone, build a square AOI, and
    return its WGS84 bounding box.

    Input axis convention:  (latitude, longitude) — (y, x) / (N, E).
    Output axis convention: [min_lon, min_lat, max_lon, max_lat] — GeoJSON (x, y).

    Args:
        latitude:    Decimal degrees north (+) / south (−).  Range: −90 … 90.
        longitude:   Decimal degrees east (+) / west (−).   Range: −180 … 180.
        half_side_m: Half the side length of the square AOI in metres.
                     Default 1 000 → 2 km × 2 km.
                     4 000 → 8 km × 8 km (large port terminals).

    Returns:
        Four-element list ``[min_lon, min_lat, max_lon, max_lat]`` in WGS84.
    """
    wgs84: CRS = CRS.from_epsg(4326)
    utm_crs: CRS = _utm_crs_for_point(latitude, longitude)

    # always_xy=True fixes the axis order to (x, y) = (lon, lat) ↔ (easting, northing)
    # regardless of the authority-defined axis order of either CRS.  Without this flag
    # pyproj >= 2.2 honours EPSG axis order for geographic CRSes, silently swapping
    # lat and lon and producing plausible-but-wrong coordinates.
    to_utm: Transformer = Transformer.from_crs(wgs84, utm_crs, always_xy=True)
    to_wgs84: Transformer = Transformer.from_crs(utm_crs, wgs84, always_xy=True)

    easting, northing = to_utm.transform(longitude, latitude)
    logger.debug("UTM easting=%.2f  northing=%.2f", easting, northing)

    square_utm = box(
        easting - half_side_m,
        northing - half_side_m,
        easting + half_side_m,
        northing + half_side_m,
    )

    # shapely.ops.transform calls to_wgs84.transform(x_array, y_array) where
    # x = easting and y = northing; with always_xy=True the return is (lon, lat).
    square_wgs84 = shapely_transform(to_wgs84.transform, square_utm)
    min_lon, min_lat, max_lon, max_lat = square_wgs84.bounds

    logger.info(
        "AOI bbox  lat=%.6f lon=%.6f → [%.6f, %.6f, %.6f, %.6f]",
        latitude,
        longitude,
        min_lon,
        min_lat,
        max_lon,
        max_lat,
    )
    return [min_lon, min_lat, max_lon, max_lat]
