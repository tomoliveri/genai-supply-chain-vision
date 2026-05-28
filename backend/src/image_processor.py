from __future__ import annotations

import io
import logging
from collections.abc import Sequence
from typing import Final

import numpy as np
import rasterio
import rasterio.io
import rasterio.windows
from affine import Affine
import google.cloud.storage as gcs
import requests
from PIL import Image
from pyproj import CRS, Transformer
from rasterio.crs import CRS as RasterioCRS
from rasterio.enums import Resampling
from rasterio.windows import Window

from backend.src.stac_client import BandPaths, SentinelImageResult

logger = logging.getLogger(__name__)

_GCS_PATH_TEMPLATE: Final[str] = "imagery_cache/{location_id}/{date}.jpg"
_JPEG_QUALITY: Final[int] = 85
_OUT_SIZE: Final[int] = 512  # long edge of the output JPEG in pixels

_GDAL_VSICURL_ENV: Final[dict[str, str]] = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".jp2,.tif,.tiff",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "GDAL_HTTP_VERSION": "2",
}

# GDAL env for local/in-memory opens — no HTTP tuning needed.
_GDAL_LOCAL_ENV: Final[dict[str, str]] = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
}

_REQUESTS_TIMEOUT: Final[int] = 300  # seconds; JP2 files can be 50–150 MB


class OutsideTileBoundsError(ValueError):
    """The requested WGS84 bounding box falls entirely outside the tile extent."""


def _compute_utm_window(
    tile_crs: RasterioCRS,
    tile_transform: Affine,
    tile_width: int,
    tile_height: int,
    bbox_wgs84: Sequence[float],
) -> Window:
    """
    Project *bbox_wgs84* from WGS84 into *tile_crs*, compute the pixel window
    using the tile's affine transform, and clamp it to [0, tile_width] ×
    [0, tile_height] to prevent IndexError at tile edges.

    Bbox axis convention: [min_lon, min_lat, max_lon, max_lat] — GeoJSON (x, y).

    Returns:
        Clamped :class:`rasterio.windows.Window` ready for ``dataset.read()``.

    Raises:
        OutsideTileBoundsError: If the bbox falls completely outside the tile.
    """
    wgs84 = CRS.from_epsg(4326)
    to_tile = Transformer.from_crs(wgs84, tile_crs, always_xy=True)

    min_lon, min_lat, max_lon, max_lat = bbox_wgs84

    # Transform all four bbox corners and take the envelope in the tile CRS so
    # that CRS distortion near the antimeridian or at high latitudes is handled.
    xs, ys = to_tile.transform(
        [min_lon, max_lon, min_lon, max_lon],
        [min_lat, min_lat, max_lat, max_lat],
    )
    utm_min_x, utm_max_x = float(min(xs)), float(max(xs))
    utm_min_y, utm_max_y = float(min(ys)), float(max(ys))

    logger.debug(
        "AOI in tile CRS: E [%.1f, %.1f]  N [%.1f, %.1f]",
        utm_min_x, utm_max_x, utm_min_y, utm_max_y,
    )

    raw_window = rasterio.windows.from_bounds(
        utm_min_x, utm_min_y, utm_max_x, utm_max_y,
        transform=tile_transform,
    )

    # Clamp to tile pixel space.  from_bounds can return negative offsets or
    # values beyond tile_width/height when the bbox extends past the tile edge.
    col_off = max(0.0, raw_window.col_off)
    row_off = max(0.0, raw_window.row_off)
    col_end = min(float(tile_width), raw_window.col_off + raw_window.width)
    row_end = min(float(tile_height), raw_window.row_off + raw_window.height)

    logger.debug(
        "Window (clamped): col [%.1f, %.1f]  row [%.1f, %.1f]",
        col_off, col_end, row_off, row_end,
    )

    if col_end <= col_off or row_end <= row_off:
        raise OutsideTileBoundsError(
            f"Bbox {list(bbox_wgs84)} falls entirely outside the tile "
            f"(col [{col_off:.0f},{col_end:.0f}] row [{row_off:.0f},{row_end:.0f}])"
        )

    return Window(
        col_off=col_off,
        row_off=row_off,
        width=col_end - col_off,
        height=row_end - row_off,
    )


def _read_clipped_rgb(
    ds: rasterio.DatasetReader,
    bbox_wgs84: Sequence[float],
    out_size: int,
) -> np.ndarray:
    """
    Compute the pixel window for *bbox_wgs84* within the open dataset *ds*,
    read only that window via HTTP range requests, and return a uint8 RGB
    array resampled to *out_size* on the long edge.

    Args:
        ds:          Open rasterio dataset (TCI has 3 bands; band files have 1).
        bbox_wgs84:  [min_lon, min_lat, max_lon, max_lat] in WGS84.
        out_size:    Long-edge pixel count of the returned array.

    Returns:
        ``np.ndarray`` of shape (H, W, 3), dtype uint8, RGB channel order.
    """
    window = _compute_utm_window(
        ds.crs, ds.transform, ds.width, ds.height, bbox_wgs84
    )

    # Preserve aspect ratio so the AOI is not stretched.
    win_w, win_h = window.width, window.height
    if win_w >= win_h:
        out_w = out_size
        out_h = max(1, round(out_size * win_h / win_w))
    else:
        out_h = out_size
        out_w = max(1, round(out_size * win_w / win_h))

    logger.debug(
        "Reading %dx%d raw pixels → %dx%d output",
        round(win_w), round(win_h), out_w, out_h,
    )

    # Reading with out_shape performs the resampling in a single GDAL call,
    # avoiding allocation of the full-resolution intermediate array.
    data = ds.read(
        window=window,
        out_shape=(ds.count, out_h, out_w),
        resampling=Resampling.lanczos,
    )

    # data shape is (bands, H, W); transpose to (H, W, bands) for PIL.
    rgb = np.transpose(data, (1, 2, 0))

    # TCI is uint8 already; individual band files are uint16 (0–10000 SR).
    if rgb.dtype != np.uint8:
        rgb = np.clip((rgb / 10000.0) * 255.0, 0, 255).astype(np.uint8)

    # If a single-band file was supplied, replicate to 3-channel greyscale.
    if rgb.shape[2] == 1:
        rgb = np.repeat(rgb, 3, axis=2)

    return rgb


def _resolve_tci_url(image_result: SentinelImageResult) -> str:
    """
    Return the HTTPS URL of the TCI asset from *image_result*.

    Prefers the pre-composited TCI (one range request) over stacking three
    individual band files.  Falls back to the B04 path with a name substitution
    if the TCI field is absent — the CDSE naming convention is stable enough
    that this fallback is reliable in practice.

    Raises:
        ValueError: If no HTTPS URL can be resolved.
    """
    tci: BandPaths | None = image_result["tci"]
    if tci is not None:
        https = tci["https"]
        if https is not None:
            return https

    b04_https: str | None = image_result["assets"]["B04"]["https"]
    if b04_https is not None:
        # Replace the band-name segment; TCI follows the same naming pattern.
        derived: str = b04_https.replace("B04_10m.jp2", "TCI_10m.jp2")
        logger.debug("TCI URL derived from B04 path: %s", derived)
        return derived

    raise ValueError(
        f"Cannot resolve a TCI HTTPS URL for product {image_result['product_id']!r}; "
        "no tci field and no B04 https path available."
    )


def _stream_download(url: str, auth_token: str | None) -> bytes:
    """
    Download *url* to memory using requests, streaming in 1 MiB chunks.

    CDSE TCI JP2 files are typically 30–150 MB.  We use requests rather than
    GDAL vsicurl for authenticated downloads because GDAL's HTTP/2 stack can
    silently drop the Authorization header in some libcurl builds, returning a
    misleading "does not exist in the file system" error for a 401 response.

    Args:
        url:         Direct HTTPS URL of the file.
        auth_token:  CDSE OIDC Bearer token, or ``None`` for public files.

    Returns:
        Raw file bytes.

    Raises:
        requests.HTTPError: Non-2xx HTTP response (includes 401/403).
    """
    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    logger.info("Downloading tile via requests: %s", url[:80] + "…")
    with requests.get(url, headers=headers, timeout=_REQUESTS_TIMEOUT, stream=True) as resp:
        resp.raise_for_status()
        content_length = resp.headers.get("Content-Length", "unknown")
        logger.debug("Content-Length: %s", content_length)
        buf = io.BytesIO()
        for chunk in resp.iter_content(chunk_size=1 << 20):
            buf.write(chunk)
    total = buf.tell()
    logger.info("Download complete: %.1f MB", total / 1_048_576)
    buf.seek(0)
    return buf.getvalue()


def crop_and_downscale(
    tci_https_url: str,
    bbox_wgs84: Sequence[float],
    auth_token: str | None = None,
    out_size: int = _OUT_SIZE,
) -> np.ndarray:
    """
    Fetch the TCI file and return a downscaled uint8 RGB array cropped to
    *bbox_wgs84*.

    When *auth_token* is provided the file is downloaded via ``requests``
    (reliable auth, follows redirects) then opened from memory.  Without a
    token the file is opened directly via GDAL ``/vsicurl/`` (public COGs).

    Args:
        tci_https_url:  HTTPS path to the TCI JPEG-2000 on CDSE.
        bbox_wgs84:     [min_lon, min_lat, max_lon, max_lat] in WGS84.
        auth_token:     CDSE OIDC Bearer token; required for live CDSE access.
        out_size:       Long-edge pixel count for the returned image.

    Returns:
        uint8 ndarray of shape (H, W, 3), RGB channel order.

    Raises:
        OutsideTileBoundsError: Bbox is entirely outside the tile extent.
        requests.HTTPError:     Auth failure or other HTTP error (authenticated path).
        rasterio.errors.RasterioIOError: File not accessible (unauthenticated path).
    """
    if auth_token:
        # Download with requests so that the Authorization header is delivered
        # reliably, then open from a MemoryFile for windowed rasterio reads.
        raw = _stream_download(tci_https_url, auth_token)
        with rasterio.Env(**_GDAL_LOCAL_ENV):
            with rasterio.io.MemoryFile(raw) as memfile:
                with memfile.open() as ds:
                    logger.debug(
                        "Tile metadata: CRS=%s  size=%dx%d  bands=%d",
                        ds.crs, ds.width, ds.height, ds.count,
                    )
                    return _read_clipped_rgb(ds, bbox_wgs84, out_size)
    else:
        vsicurl_url = f"/vsicurl/{tci_https_url}"
        logger.info("Opening public tile via vsicurl: %s", tci_https_url[:80] + "…")
        with rasterio.Env(**_GDAL_VSICURL_ENV):
            with rasterio.open(vsicurl_url) as ds:
                logger.debug(
                    "Tile metadata: CRS=%s  size=%dx%d  bands=%d",
                    ds.crs, ds.width, ds.height, ds.count,
                )
                return _read_clipped_rgb(ds, bbox_wgs84, out_size)


def _encode_jpeg_bytes(
    image_array: np.ndarray,
    jpeg_quality: int = _JPEG_QUALITY,
) -> bytes:
    """Encode a uint8 (H, W, 3) RGB array as JPEG bytes in memory."""
    buf = io.BytesIO()
    img = Image.fromarray(image_array, mode="RGB")
    img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    return buf.getvalue()


def _gcs_path_for(location_id: str, capture_date: str) -> str:
    """Return the GCS blob path for an imagery JPEG."""
    return _GCS_PATH_TEMPLATE.format(location_id=location_id, date=capture_date[:10])


def upload_to_gcs(
    image_array: np.ndarray,
    location_id: str,
    capture_date: str,
    bucket_name: str,
    jpeg_quality: int = _JPEG_QUALITY,
) -> str:
    """
    Encode *image_array* as a JPEG and upload it to GCS.

    Args:
        image_array:   uint8 (H, W, 3) RGB array.
        location_id:   Identifier used to namespace the GCS path.
        capture_date:  ISO 8601 date string; only the YYYY-MM-DD portion is used.
        bucket_name:   GCS bucket name (must already exist).
        jpeg_quality:  JPEG compression quality (1–95).

    Returns:
        ``gs://`` URI of the uploaded object.
    """
    gcs_path = _gcs_path_for(location_id, capture_date)
    jpeg_bytes = _encode_jpeg_bytes(image_array, jpeg_quality)

    client = gcs.Client()
    blob = client.bucket(bucket_name).blob(gcs_path)
    blob.upload_from_string(jpeg_bytes, content_type="image/jpeg")

    gcs_uri = f"gs://{bucket_name}/{gcs_path}"
    logger.info("Uploaded imagery to %s (%d bytes)", gcs_uri, len(jpeg_bytes))
    return gcs_uri


def process_and_upload(
    image_result: SentinelImageResult,
    bbox_wgs84: Sequence[float],
    location_id: str,
    bucket_name: str,
    auth_token: str | None = None,
    out_size: int = _OUT_SIZE,
    jpeg_quality: int = _JPEG_QUALITY,
) -> str:
    """
    End-to-end pipeline: discover → crop → downscale → upload.

    Resolves the TCI URL from *image_result*, reads only the AOI pixel window
    from the remote tile, and uploads the result to GCS.

    Args:
        image_result:  Output of :func:`~backend.src.stac_client.get_latest_sentinel_image`.
        bbox_wgs84:    [min_lon, min_lat, max_lon, max_lat] in WGS84.
        location_id:   GCS path namespace for this watchlist location.
        bucket_name:   GCS destination bucket.
        auth_token:    CDSE OIDC Bearer token for remote tile access.
        out_size:      Long-edge pixel count for the stored JPEG.
        jpeg_quality:  JPEG compression quality (1–95).

    Returns:
        ``gs://`` URI of the uploaded JPEG.
    """
    tci_url = _resolve_tci_url(image_result)
    rgb = crop_and_downscale(tci_url, bbox_wgs84, auth_token, out_size)
    return upload_to_gcs(rgb, location_id, image_result["capture_date"], bucket_name, jpeg_quality)


def process_to_bytes(
    image_result: SentinelImageResult,
    bbox_wgs84: Sequence[float],
    location_id: str,
    bucket_name: str,
    auth_token: str | None = None,
    out_size: int = _OUT_SIZE,
    jpeg_quality: int = _JPEG_QUALITY,
) -> tuple[str, bytes]:
    """
    End-to-end pipeline: discover → crop → downscale → upload + return bytes.

    Like :func:`process_and_upload` but also returns the JPEG bytes so callers
    (e.g. backfill) can feed them directly to Gemini without a redundant GCS
    download.  Returns ``(gs_uri, jpeg_bytes)``.

    Args:
        image_result:  Output of :func:`~backend.src.stac_client.get_latest_sentinel_image`.
        bbox_wgs84:    [min_lon, min_lat, max_lon, max_lat] in WGS84.
        location_id:   GCS path namespace for this watchlist location.
        bucket_name:   GCS destination bucket.
        auth_token:    CDSE OIDC Bearer token for remote tile access.
        out_size:      Long-edge pixel count for the stored JPEG.
        jpeg_quality:  JPEG compression quality (1–95).

    Returns:
        ``(gs_uri, jpeg_bytes)`` tuple.
    """
    tci_url = _resolve_tci_url(image_result)
    rgb = crop_and_downscale(tci_url, bbox_wgs84, auth_token, out_size)

    jpeg_bytes = _encode_jpeg_bytes(rgb, jpeg_quality)
    gcs_path = _gcs_path_for(location_id, image_result["capture_date"])

    client = gcs.Client()
    blob = client.bucket(bucket_name).blob(gcs_path)
    blob.upload_from_string(jpeg_bytes, content_type="image/jpeg")

    gcs_uri = f"gs://{bucket_name}/{gcs_path}"
    logger.info("Uploaded imagery to %s (%d bytes)", gcs_uri, len(jpeg_bytes))
    return gcs_uri, jpeg_bytes
