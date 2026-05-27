from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Final, TypedDict

from pystac import Asset, Item
from pystac_client import Client
from pystac_client.exceptions import APIError

logger = logging.getLogger(__name__)

_CDSE_STAC_URL: Final[str] = "https://catalogue.dataspace.copernicus.eu/stac"
_COLLECTION: Final[str] = "sentinel-2-l2a"

# Maps the logical band name the caller sees to the actual STAC asset key.
# CDSE names band assets with a resolution suffix; 10 m is the native
# resolution for the visual bands and gives the sharpest imagery.
_BAND_ASSET_KEYS: Final[dict[str, str]] = {
    "B04": "B04_10m",  # Red
    "B03": "B03_10m",  # Green
    "B02": "B02_10m",  # Blue
}

# Fetch a small pool so the client-side cloud/asset filter has room to work
# even when the server-side query extension returns border-case values.
_CANDIDATE_POOL: Final[int] = 10

# TCI (True Color Image) is a pre-composited 3-band uint8 RGB asset — one
# remote read versus three reads for individual bands.
_TCI_ASSET_KEY: Final[str] = "TCI_10m"


class BandPaths(TypedDict):
    """Storage paths for a single 10 m-resolution Sentinel-2 band."""

    s3: str           # CloudFerro/CreoDIAS S3 — primary path for on-cloud processing
    https: str | None  # CDSE HTTPS download — requires OIDC authentication


class VisualAssets(TypedDict):
    """10 m RGB band paths for a Sentinel-2 L2A scene."""

    B04: BandPaths  # Red    (665 nm)
    B03: BandPaths  # Green  (560 nm)
    B02: BandPaths  # Blue   (493 nm)


class SentinelImageResult(TypedDict):
    """Normalised metadata returned by :func:`get_latest_sentinel_image`."""

    product_id: str          # Full STAC item ID / product safe-name
    capture_date: str        # ISO 8601 UTC timestamp of the scene acquisition
    cloud_cover: float       # Scene-level cloud cover in percent (0 – 100)
    assets: VisualAssets
    tci: BandPaths | None    # Pre-composited RGB; None if absent from the STAC item


def _asset_paths(asset: Asset) -> BandPaths:
    """Extract S3 href and HTTPS alternate from a STAC Asset object."""
    https_href: str | None = (
        asset.extra_fields
        .get("alternate", {})
        .get("https", {})
        .get("href")
    )
    return BandPaths(s3=asset.href, https=https_href)


def _extract_visual_assets(item: Item) -> VisualAssets | None:
    """
    Extract S3 and HTTPS paths for the three visual bands from a STAC item.

    Returns None if any band asset is absent so that callers never receive a
    partially-populated result that would fail silently during raster access.
    """
    paths: dict[str, BandPaths] = {}

    for logical_name, asset_key in _BAND_ASSET_KEYS.items():
        if asset_key not in item.assets:
            logger.warning("Item %s is missing asset %r — skipping", item.id, asset_key)
            return None
        paths[logical_name] = _asset_paths(item.assets[asset_key])

    return VisualAssets(B04=paths["B04"], B03=paths["B03"], B02=paths["B02"])


def get_latest_sentinel_image(
    bbox: Sequence[float],
    max_cloud_cover: float = 10.0,
) -> SentinelImageResult | None:
    """
    Query CDSE STAC for the most recent Sentinel-2 L2A scene within *bbox*
    whose cloud cover does not exceed *max_cloud_cover* percent.

    Bbox axis convention (input): [min_lon, min_lat, max_lon, max_lat] — GeoJSON (x, y).

    The function applies a server-side cloud-cover filter via the STAC
    ``query`` extension and also re-verifies the property client-side before
    returning, so the result is guaranteed to meet the threshold regardless
    of API edge-case behaviour.

    Args:
        bbox:             [min_lon, min_lat, max_lon, max_lat] in WGS84.
        max_cloud_cover:  Maximum acceptable cloud cover (0 – 100, percent).

    Returns:
        :class:`SentinelImageResult` dict, or ``None`` if no qualifying image
        is found (empty archive window, persistent cloud cover, etc.).

    Raises:
        APIError: Propagated from pystac_client on unexpected CDSE API errors.
    """
    client = Client.open(_CDSE_STAC_URL)
    logger.debug("Connected to CDSE STAC: %s", _CDSE_STAC_URL)

    try:
        search = client.search(
            collections=[_COLLECTION],
            bbox=list(bbox),
            query={"eo:cloud_cover": {"lte": max_cloud_cover}},
            sortby=["-datetime"],
            max_items=_CANDIDATE_POOL,
        )
        items: list[Item] = list(search.items())
    except APIError as exc:
        logger.error("CDSE STAC search failed: %s", exc)
        raise

    if not items:
        logger.warning(
            "No %s images returned for bbox=%s max_cloud=%.1f%%",
            _COLLECTION,
            list(bbox),
            max_cloud_cover,
        )
        return None

    # Defensive client-side sort newest-first; the API sort may be advisory.
    items.sort(
        key=lambda i: i.datetime or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    logger.debug("Evaluating %d candidate item(s)", len(items))

    for item in items:
        cloud_raw = item.properties.get("eo:cloud_cover")
        if cloud_raw is None:
            logger.debug("Item %s has no eo:cloud_cover — skipping", item.id)
            continue

        cloud_cover = float(cloud_raw)
        if cloud_cover > max_cloud_cover:
            logger.debug(
                "Item %s cloud=%.1f%% > threshold %.1f%% — skipping",
                item.id,
                cloud_cover,
                max_cloud_cover,
            )
            continue

        visual = _extract_visual_assets(item)
        if visual is None:
            continue

        tci: BandPaths | None = (
            _asset_paths(item.assets[_TCI_ASSET_KEY])
            if _TCI_ASSET_KEY in item.assets
            else None
        )

        capture_date: str = (
            item.datetime.isoformat()
            if item.datetime is not None
            else str(item.properties.get("datetime", ""))
        )

        result = SentinelImageResult(
            product_id=item.id,
            capture_date=capture_date,
            cloud_cover=cloud_cover,
            assets=visual,
            tci=tci,
        )
        logger.info(
            "Returning image %s  date=%s  cloud=%.1f%%",
            item.id,
            capture_date,
            cloud_cover,
        )
        return result

    logger.warning(
        "All %d candidate(s) failed client-side validation (bbox=%s, max_cloud=%.1f%%)",
        len(items),
        list(bbox),
        max_cloud_cover,
    )
    return None


def get_scenes_for_period(
    bbox: Sequence[float],
    start_date: datetime,
    end_date: datetime,
    max_cloud_cover: float = 15.0,
    max_scenes: int = 24,
) -> list[SentinelImageResult]:
    """
    Query CDSE STAC for all qualifying scenes within [start_date, end_date].

    Returns at most one scene per calendar month (lowest cloud cover wins),
    sorted oldest-first, ready for consecutive-pair comparison.

    Bbox axis convention (input): [min_lon, min_lat, max_lon, max_lat] — GeoJSON (x, y).

    Args:
        bbox:             [min_lon, min_lat, max_lon, max_lat] in WGS84.
        start_date:       UTC-aware start of the query window (inclusive).
        end_date:         UTC-aware end of the query window (inclusive).
        max_cloud_cover:  Maximum acceptable cloud cover (0 – 100, percent).
        max_scenes:       Hard cap on the number of returned results.

    Returns:
        List of :class:`SentinelImageResult`, oldest-first.  May be empty if
        no qualifying scenes exist in the window.

    Raises:
        APIError: Propagated from pystac_client on unexpected CDSE API errors.
    """
    client = Client.open(_CDSE_STAC_URL)

    dt_range = (
        f"{start_date.strftime('%Y-%m-%dT%H:%M:%SZ')}/"
        f"{end_date.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )
    logger.debug("Period query: %s", dt_range)

    try:
        search = client.search(
            collections=[_COLLECTION],
            bbox=list(bbox),
            datetime=dt_range,
            query={"eo:cloud_cover": {"lte": max_cloud_cover}},
            sortby=["-datetime"],
            max_items=max_scenes * 8,
        )
        items: list[Item] = list(search.items())
    except APIError as exc:
        logger.error("CDSE STAC period search failed: %s", exc)
        raise

    items.sort(
        key=lambda i: i.datetime or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    logger.debug("Period query returned %d candidate(s)", len(items))

    best_per_month: dict[tuple[int, int], Item] = {}
    for item in items:
        cloud_raw = item.properties.get("eo:cloud_cover")
        if cloud_raw is None or float(cloud_raw) > max_cloud_cover:
            continue
        item_dt = item.datetime
        if item_dt is None:
            continue
        key = (item_dt.year, item_dt.month)
        existing = best_per_month.get(key)
        if existing is None or float(cloud_raw) < float(
            existing.properties.get("eo:cloud_cover", 100)
        ):
            best_per_month[key] = item

    results: list[SentinelImageResult] = []
    for item in sorted(
        best_per_month.values(),
        key=lambda i: i.datetime or datetime.min.replace(tzinfo=timezone.utc),
    ):
        cloud_cover = float(item.properties.get("eo:cloud_cover", 0))
        visual = _extract_visual_assets(item)
        if visual is None:
            continue

        tci: BandPaths | None = (
            _asset_paths(item.assets[_TCI_ASSET_KEY])
            if _TCI_ASSET_KEY in item.assets
            else None
        )
        capture_date: str = (
            item.datetime.isoformat()
            if item.datetime is not None
            else str(item.properties.get("datetime", ""))
        )
        results.append(
            SentinelImageResult(
                product_id=item.id,
                capture_date=capture_date,
                cloud_cover=cloud_cover,
                assets=visual,
                tci=tci,
            )
        )
        if len(results) >= max_scenes:
            break

    logger.info(
        "Period query: %d scene(s) returned for %d months searched",
        len(results),
        len(best_per_month),
    )
    return results
