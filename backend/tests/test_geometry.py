from __future__ import annotations

from typing import Final

import pytest
from pyproj import Geod

from backend.src.geometry_utils import compute_aoi_bbox

_GEOD: Final[Geod] = Geod(ellps="WGS84")

# (latitude, longitude, label)
_POINTS: Final[list[tuple[float, float, str]]] = [
    (29.8683, 121.5440, "Port of Ningbo, China"),
    (30.4254, 32.3394, "Suez Canal, Egypt"),
    (1.2644, 103.8222, "Port of Singapore (equatorial)"),
    (70.6632, 23.6821, "Tromsø, Norway (high-latitude, 70 °N)"),
    (-36.8485, 174.7633, "Port of Auckland (antimeridian-adjacent, ~175 °E)"),
]


def _geodesic_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    _, _, dist = _GEOD.inv(lon1, lat1, lon2, lat2)
    return float(dist)


@pytest.fixture(params=_POINTS, ids=[p[2] for p in _POINTS])
def sample_bbox(request: pytest.FixtureRequest) -> tuple[float, float, str, list[float]]:
    lat, lon, label = request.param
    return lat, lon, label, compute_aoi_bbox(lat, lon)


# ── CRS correctness ────────────────────────────────────────────────────────────

def test_output_crs_wgs84_lon_range(sample_bbox: tuple[float, float, str, list[float]]) -> None:
    _, _, label, (min_lon, _, max_lon, _) = sample_bbox
    assert -180.0 <= min_lon <= 180.0, f"{label}: min_lon {min_lon} outside WGS84"
    assert -180.0 <= max_lon <= 180.0, f"{label}: max_lon {max_lon} outside WGS84"


def test_output_crs_wgs84_lat_range(sample_bbox: tuple[float, float, str, list[float]]) -> None:
    _, _, label, (_, min_lat, _, max_lat) = sample_bbox
    assert -90.0 <= min_lat <= 90.0, f"{label}: min_lat {min_lat} outside WGS84"
    assert -90.0 <= max_lat <= 90.0, f"{label}: max_lat {max_lat} outside WGS84"


# ── Axis-order correctness ─────────────────────────────────────────────────────
# A lat/lon swap produces easting/northing values (~100 000 – 900 000) in the
# lon slots and tiny degree values in the lat slots, immediately violating the
# range checks above.  The ordering checks below catch subtler axis inversions
# where min and max are accidentally swapped.

def test_axis_order_lon_not_reversed(sample_bbox: tuple[float, float, str, list[float]]) -> None:
    _, _, label, (min_lon, _, max_lon, _) = sample_bbox
    assert min_lon < max_lon, f"{label}: min_lon ({min_lon}) >= max_lon ({max_lon})"


def test_axis_order_lat_not_reversed(sample_bbox: tuple[float, float, str, list[float]]) -> None:
    _, _, label, (_, min_lat, _, max_lat) = sample_bbox
    assert min_lat < max_lat, f"{label}: min_lat ({min_lat}) >= max_lat ({max_lat})"


# ── Centre proximity ───────────────────────────────────────────────────────────

def test_bbox_centre_within_10m_of_input(sample_bbox: tuple[float, float, str, list[float]]) -> None:
    lat, lon, label, (min_lon, min_lat, max_lon, max_lat) = sample_bbox
    centre_lon = (min_lon + max_lon) / 2.0
    centre_lat = (min_lat + max_lat) / 2.0
    dist_m = _geodesic_m(lon, lat, centre_lon, centre_lat)
    assert dist_m < 10.0, f"{label}: bbox centre is {dist_m:.2f} m from input (expected < 10 m)"


# ── Tile/bounding-box dimension accuracy ──────────────────────────────────────

@pytest.mark.parametrize("tolerance", [0.05])
def test_bbox_width_approx_2km(
    sample_bbox: tuple[float, float, str, list[float]], tolerance: float
) -> None:
    _, _, label, (min_lon, min_lat, max_lon, max_lat) = sample_bbox
    mid_lat = (min_lat + max_lat) / 2.0
    width_m = _geodesic_m(min_lon, mid_lat, max_lon, mid_lat)
    assert abs(width_m - 2000.0) / 2000.0 < tolerance, (
        f"{label}: width {width_m:.1f} m deviates >{tolerance*100:.0f}% from 2 000 m"
    )


@pytest.mark.parametrize("tolerance", [0.05])
def test_bbox_height_approx_2km(
    sample_bbox: tuple[float, float, str, list[float]], tolerance: float
) -> None:
    _, _, label, (min_lon, min_lat, max_lon, max_lat) = sample_bbox
    mid_lon = (min_lon + max_lon) / 2.0
    height_m = _geodesic_m(mid_lon, min_lat, mid_lon, max_lat)
    assert abs(height_m - 2000.0) / 2000.0 < tolerance, (
        f"{label}: height {height_m:.1f} m deviates >{tolerance*100:.0f}% from 2 000 m"
    )


# ── Clipping: no coordinate escapes WGS84 world bounds ────────────────────────

def test_all_corners_within_wgs84_bounds(sample_bbox: tuple[float, float, str, list[float]]) -> None:
    _, _, label, (min_lon, min_lat, max_lon, max_lat) = sample_bbox
    corners = [
        (min_lon, min_lat),
        (max_lon, min_lat),
        (max_lon, max_lat),
        (min_lon, max_lat),
    ]
    for clon, clat in corners:
        assert -180.0 <= clon <= 180.0, f"{label}: corner lon {clon} outside WGS84"
        assert -90.0 <= clat <= 90.0, f"{label}: corner lat {clat} outside WGS84"
