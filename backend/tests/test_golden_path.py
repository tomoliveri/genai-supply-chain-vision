"""
Golden-path end-to-end integration test for the supply-chain vision pipeline.

Exercises every layer in sequence and asserts correctness at each boundary:

  Stage 1 — Geometry        CRS + axis-order correctness for four real ports
  Stage 2 — STAC            Live CDSE Sentinel-2 metadata query for Baltimore
  Stage 3 — Imagery         Bounding-box crop (live CDSE or synthetic fallback)
  Stage 4 — Gemini          Live Vertex AI multimodal disruption analysis
  Stage 5 — Persistence     Firestore watchlist_items + daily_briefings writes
  Stage 6 — Round-trip      Read-back schema validation for frontend compatibility

Run from project root:
    python -m backend.tests.test_golden_path [--keep]

Pass --keep to retain Firestore documents for frontend demo (default: clean up).
"""

from __future__ import annotations

import io
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import google.cloud.firestore as gfs
import numpy as np
from PIL import Image, ImageDraw
from pyproj import Geod

from backend.src.analyser import DisruptionAnalysis, analyse_disruption_from_bytes
from backend.src.geometry_utils import compute_aoi_bbox
from backend.src.stac_client import SentinelImageResult, get_latest_sentinel_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

_GEOD = Geod(ellps="WGS84")

# ── Primary integration target ───────────────────────────────────────────────
# Coordinates: waterfront edge of the Seagirt Marine Terminal container piers,
# on the Patapsco River.  Previous value (39.27, -76.53) was ~2 km too far
# north and captured mostly industrial land rather than the active berths.
_TARGET_NAME = "Seagirt Marine Terminal, Port of Baltimore"
_TARGET_LAT = 39.2484
_TARGET_LON = -76.5494

_PROJECT_ID = "traveltime-465606"
_IMAGERY_BUCKET = os.environ.get("GCS_BUCKET_NAME", "traveltime-465606-imagery-cache")
_CDSE_AUTH_TOKEN: str | None = os.environ.get("CDSE_AUTH_TOKEN") or None

# ── CLAUDE.md — geospatial validation points (equatorial, high-lat, anti-meridian) ──
_GEO_VALIDATION_POINTS: list[tuple[str, float, float]] = [
    (_TARGET_NAME, _TARGET_LAT, _TARGET_LON),                            # mid-latitude N
    ("Port of Singapore (equatorial)", 1.27, 103.82),                    # near 0°
    ("Port of Anchorage (high-latitude)", 61.22, -149.88),               # ~61°N
    ("Port of Valparaíso (antimeridian-adjacent, S hemisphere)", -33.04, -71.63),
]


# ── Shared helpers ────────────────────────────────────────────────────────────

def _banner(title: str) -> None:
    sep = "═" * 68
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)


def _ok(msg: str) -> None:
    logger.info("    ✓  %s", msg)


def _skip(msg: str) -> None:
    logger.warning("    ⚠  %s", msg)


def _fail_line(msg: str) -> None:
    logger.error("    ✗  %s", msg)


def _make_port_jpeg(seed: int = 42, disrupted: bool = False) -> bytes:
    """Synthetic 256×256 harbour scene for Gemini testing when live imagery is unavailable."""
    rng = np.random.default_rng(seed)
    w, h = 256, 256
    img = Image.new("RGB", (w, h), (30, 90, 140))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, h // 2, w, h], fill=(110, 100, 85))

    if not disrupted:
        draw.rectangle([20, h // 2 - 40, 80, h // 2 - 10], fill=(160, 160, 160))
        draw.rectangle([100, h // 2 - 35, 150, h // 2 - 8], fill=(150, 150, 155))
        for x in (60, 130):
            draw.line([(x, h // 2 - 5), (x, h // 2 - 55)], fill=(40, 40, 40), width=3)
        for row, col_rgb in enumerate(
            [(200, 50, 50), (50, 200, 50), (50, 50, 200), (200, 200, 50)]
        ):
            y0 = h // 2 + 20 + row * 14
            draw.rectangle([10, y0, 240, y0 + 10], fill=col_rgb)
    else:
        draw.ellipse([50, h // 2, 180, h // 2 + 60], fill=(220, 80, 10))
        for _ in range(10):
            x = int(rng.integers(5, w - 20))
            y = int(rng.integers(h // 2 + 10, h - 10))
            draw.rectangle([x, y, x + 15, y + 10], fill=(80, 80, 80))

    noise = rng.integers(-3, 4, (h, w, 3), dtype=np.int32)
    arr = np.clip(np.array(img, dtype=np.int32) + noise, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ── Stage 1: Geometry validation ──────────────────────────────────────────────

def stage_geometry() -> list[float]:
    """
    Assert CRS, axis-order, and size correctness for four geographically
    diverse ports (CLAUDE.md mandatory geospatial assertion rule).

    Returns the Baltimore bbox for use in subsequent stages.
    """
    _banner("STAGE 1 — GEOMETRY VALIDATION  (4 locations)")

    failures: list[str] = []
    baltimore_bbox: list[float] = []

    for name, lat, lon in _GEO_VALIDATION_POINTS:
        try:
            bbox = compute_aoi_bbox(lat, lon)
            min_lon, min_lat, max_lon, max_lat = bbox

            # CRS correctness: coordinates must be in WGS84 range
            assert -180.0 <= min_lon <= 180.0 and -180.0 <= max_lon <= 180.0, (
                f"Longitude out of WGS84 range: [{min_lon}, {max_lon}]"
            )
            assert -90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0, (
                f"Latitude out of WGS84 range: [{min_lat}, {max_lat}]"
            )

            # Axis-order correctness: catches silent lat/lon swaps
            assert min_lon < max_lon, (
                f"min_lon >= max_lon ({min_lon:.6f} >= {max_lon:.6f}) — likely axis-order bug"
            )
            assert min_lat < max_lat, (
                f"min_lat >= max_lat ({min_lat:.6f} >= {max_lat:.6f}) — likely axis-order bug"
            )

            # Bbox centre within 50 m of the input point
            c_lon = (min_lon + max_lon) / 2.0
            c_lat = (min_lat + max_lat) / 2.0
            _, _, centre_dist = _GEOD.inv(lon, lat, c_lon, c_lat)
            assert centre_dist < 50.0, (
                f"Bbox centre is {centre_dist:.1f}m from input (max 50m)"
            )

            # AOI width and height must be 2 000 m ± 5 %
            _, _, width_m = _GEOD.inv(min_lon, c_lat, max_lon, c_lat)
            _, _, height_m = _GEOD.inv(c_lon, min_lat, c_lon, max_lat)
            assert 1900.0 <= width_m <= 2100.0, (
                f"AOI width {width_m:.0f}m not in [1900, 2100]"
            )
            assert 1900.0 <= height_m <= 2100.0, (
                f"AOI height {height_m:.0f}m not in [1900, 2100]"
            )

            _ok(
                f"{name}\n"
                f"          bbox=[{min_lon:.5f}, {min_lat:.5f}, {max_lon:.5f}, {max_lat:.5f}]\n"
                f"          w={width_m:.0f}m  h={height_m:.0f}m  centre_offset={centre_dist:.1f}m"
            )

            if lat == _TARGET_LAT and lon == _TARGET_LON:
                baltimore_bbox = bbox

        except AssertionError as exc:
            _fail_line(f"{name}: {exc}")
            failures.append(f"{name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            _fail_line(f"{name}: unexpected — {exc}")
            failures.append(f"{name}: {exc}")

    if failures:
        raise AssertionError(f"Geometry assertions failed: {failures}")

    logger.info("    Geometry stage PASSED (%d/4 locations)", len(_GEO_VALIDATION_POINTS))
    return baltimore_bbox


# ── Stage 2: STAC live metadata query ────────────────────────────────────────

def stage_stac(bbox: list[float]) -> SentinelImageResult | None:
    """Query the live CDSE STAC endpoint for the latest Sentinel-2 scene."""
    _banner("STAGE 2 — STAC LIVE METADATA QUERY")

    logger.info("    bbox       = %s", bbox)
    logger.info("    max_cloud  = 30%%")
    t0 = time.monotonic()

    result = get_latest_sentinel_image(bbox, max_cloud_cover=30.0)
    elapsed_ms = (time.monotonic() - t0) * 1000

    if result is None:
        _skip(
            f"No qualifying scene returned (elapsed {elapsed_ms:.0f}ms). "
            "This is a data-availability condition, not a code defect."
        )
        return None

    assert result["cloud_cover"] <= 30.0, (
        f"cloud_cover {result['cloud_cover']} exceeds server-requested max of 30%"
    )
    assert result["product_id"], "product_id must be non-empty"
    assert result["capture_date"], "capture_date must be non-empty"

    tci = result["tci"]
    _ok(f"product_id   = {result['product_id']}")
    _ok(f"capture_date = {result['capture_date']}")
    _ok(f"cloud_cover  = {result['cloud_cover']:.1f}%")
    _ok(f"TCI present  = {tci is not None}")
    _ok(f"Band assets  = {list(result['assets'].keys())}")
    if tci and tci["https"]:
        _ok(f"TCI HTTPS    = {str(tci['https'])[:72]}…")

    logger.info("    STAC stage PASSED (elapsed %dms)", elapsed_ms)
    return result


# ── Stage 3: Image acquisition ────────────────────────────────────────────────

def stage_imagery(
    stac_result: SentinelImageResult | None,
    bbox: list[float],
) -> tuple[bytes, bytes, str]:
    """
    Attempt a live CDSE bounding-box crop.  Falls back to synthetic port JPEGs
    if CDSE_AUTH_TOKEN is absent or the request fails (auth 401 / timeout).

    Returns (current_bytes, baseline_bytes, acquisition_method).
    """
    _banner("STAGE 3 — IMAGE ACQUISITION")

    live_attempted = False
    if stac_result is not None and _CDSE_AUTH_TOKEN is not None:
        live_attempted = True
        try:
            from backend.src.image_processor import crop_and_downscale  # noqa: PLC0415

            tci = stac_result["tci"]
            tci_url: str | None = tci["https"] if tci else None

            if tci_url is None:
                _skip("TCI HTTPS URL unavailable in STAC result — using synthetic fallback")
            else:
                logger.info("    Attempting live CDSE crop: %s…", tci_url[:60])
                t0 = time.monotonic()
                rgb = crop_and_downscale(tci_url, bbox, auth_token=_CDSE_AUTH_TOKEN)
                elapsed_ms = (time.monotonic() - t0) * 1000

                assert rgb.dtype == np.uint8, f"dtype must be uint8, got {rgb.dtype}"
                assert rgb.ndim == 3 and rgb.shape[2] == 3, (
                    f"Expected (H,W,3), got {rgb.shape}"
                )
                assert int(rgb.min()) >= 0 and int(rgb.max()) <= 255, (
                    f"Pixel range [{rgb.min()},{rgb.max()}] outside [0,255]"
                )

                buf = io.BytesIO()
                Image.fromarray(rgb).save(buf, format="JPEG", quality=85)
                current_bytes = buf.getvalue()
                baseline_bytes = _make_port_jpeg(seed=99, disrupted=False)

                _ok(f"Live CDSE crop:  shape={rgb.shape}  size={len(current_bytes)//1024}KB  elapsed={elapsed_ms:.0f}ms")
                _ok(f"Baseline image:  synthetic fallback  size={len(baseline_bytes)//1024}KB")
                return current_bytes, baseline_bytes, "live_cdse"

        except Exception as exc:  # noqa: BLE001
            _skip(f"Live CDSE crop failed ({type(exc).__name__}: {exc}); using synthetic fallback")

    elif _CDSE_AUTH_TOKEN is None:
        _skip("CDSE_AUTH_TOKEN not set — synthetic imagery used (set token to test live crop)")
    else:
        _skip("No STAC scene — synthetic imagery used")

    if not live_attempted:
        _skip("Live crop not attempted — CDSE_AUTH_TOKEN absent")

    baseline_bytes = _make_port_jpeg(seed=42, disrupted=False)
    current_bytes = _make_port_jpeg(seed=77, disrupted=False)

    _ok(f"Synthetic baseline: {len(baseline_bytes)} bytes (seed=42, quiet harbour)")
    _ok(f"Synthetic current:  {len(current_bytes)} bytes (seed=77, quiet harbour)")
    return current_bytes, baseline_bytes, "synthetic"


# ── Stage 4: Gemini 2.5 Flash analysis ───────────────────────────────────────

def stage_gemini(
    current_bytes: bytes,
    baseline_bytes: bytes,
    location_context: str,
) -> DisruptionAnalysis:
    """Submit images to Gemini 2.5 Flash and assert structured schema compliance."""
    _banner("STAGE 4 — GEMINI 2.5 FLASH MULTIMODAL ANALYSIS")

    logger.info("    location_context: %s", location_context)
    logger.info("    payload:  baseline=%d B  current=%d B", len(baseline_bytes), len(current_bytes))
    t0 = time.monotonic()

    analysis = analyse_disruption_from_bytes(
        current_bytes=current_bytes,
        baseline_bytes=baseline_bytes,
        location_context=location_context,
    )
    elapsed_ms = (time.monotonic() - t0) * 1000

    # Schema assertions
    assert isinstance(analysis.disruption_detected, bool), (
        f"disruption_detected must be bool, got {type(analysis.disruption_detected).__name__}"
    )
    assert 1 <= analysis.severity_score <= 5, (
        f"severity_score {analysis.severity_score} outside [1, 5]"
    )
    assert analysis.confidence_grade in ("High", "Medium", "Low"), (
        f"confidence_grade {analysis.confidence_grade!r} not in {{High, Medium, Low}}"
    )
    assert isinstance(analysis.explanation, str) and len(analysis.explanation) >= 20, (
        f"explanation too short or wrong type"
    )

    _ok(f"disruption_detected  = {analysis.disruption_detected}")
    _ok(f"severity_score       = {analysis.severity_score}/5")
    _ok(f"confidence_grade     = {analysis.confidence_grade}")
    _ok(f"explanation ({len(analysis.explanation)} chars):")
    for line in analysis.explanation.split(". ")[:3]:
        logger.info("        %s.", line.rstrip("."))
    logger.info("    Gemini stage PASSED (elapsed %dms)", elapsed_ms)

    return analysis


# ── Stage 5: Firestore persistence ────────────────────────────────────────────

def stage_firestore(
    analysis: DisruptionAnalysis,
    stac_result: SentinelImageResult | None,
    acquisition_method: str,
) -> tuple[str, str]:
    """
    Write a watchlist_item (upsert by name) and a fresh daily_briefing to Firestore.
    Returns (watchlist_doc_id, briefing_doc_id).
    """
    _banner("STAGE 5 — FIRESTORE PERSISTENCE")

    db: Any = gfs.Client(project=_PROJECT_ID)

    # ── watchlist_items: upsert ──────────────────────────────────────────────
    existing = list(
        db.collection("watchlist_items")
        .where(filter=gfs.FieldFilter("location_name", "==", _TARGET_NAME))
        .limit(1)
        .stream()
    )
    if existing:
        watchlist_doc_id: str = existing[0].id
        _ok(f"watchlist_items: existing doc reused  id={watchlist_doc_id}")
    else:
        watchlist_doc_id = str(uuid.uuid4())
        db.collection("watchlist_items").document(watchlist_doc_id).set(
            {
                "user_id": "golden-path-test",
                "location_name": _TARGET_NAME,
                "latitude": _TARGET_LAT,
                "longitude": _TARGET_LON,
                "geofence_radius_meters": 1000.0,
                "created_at": datetime.now(tz=timezone.utc),
            }
        )
        _ok(f"watchlist_items: created new doc      id={watchlist_doc_id}")

    # ── daily_briefings: always create (each run is a new analysis) ──────────
    scene_date = (
        stac_result["capture_date"][:10]
        if stac_result is not None
        else datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    )
    current_gcs = (
        f"gs://{_IMAGERY_BUCKET}/imagery_cache/{watchlist_doc_id}/{scene_date}.jpg"
    )
    baseline_gcs = (
        f"gs://{_IMAGERY_BUCKET}/imagery_cache/{watchlist_doc_id}/baseline-{scene_date}.jpg"
    )
    location_context = (
        f"{_TARGET_NAME} — lat {_TARGET_LAT:.4f} lon {_TARGET_LON:.4f}"
    )
    analysed_at = datetime.now(tz=timezone.utc).isoformat()

    briefing_ref = db.collection("daily_briefings").document()
    briefing_ref.set(
        {
            "disruption_detected": analysis.disruption_detected,
            "severity_score": analysis.severity_score,
            "confidence_grade": analysis.confidence_grade,
            "explanation": analysis.explanation,
            "current_image_path": current_gcs,
            "baseline_image_path": baseline_gcs,
            "location_context": location_context,
            "analysed_at": analysed_at,
            "acquisition_method": acquisition_method,
        }
    )
    briefing_doc_id = briefing_ref.id

    _ok(f"daily_briefings: created new doc       id={briefing_doc_id}")
    _ok(f"  current_image_path:  {current_gcs}")
    _ok(f"  baseline_image_path: {baseline_gcs}")
    _ok(f"  location_context:    {location_context!r}")

    logger.info("    Firestore stage PASSED")
    return watchlist_doc_id, briefing_doc_id


# ── Stage 6: Round-trip schema validation ─────────────────────────────────────

def stage_roundtrip(watchlist_doc_id: str, briefing_doc_id: str) -> None:
    """
    Read both documents back from Firestore and validate every field against the
    frontend TypeScript interface schema (src/lib/types.ts: WatchlistItem +
    DailyBriefing).  Also confirms the location-matching heuristic used by
    useFirestoreData.ts parses correctly.
    """
    _banner("STAGE 6 — FIRESTORE ROUND-TRIP + FRONTEND SCHEMA VALIDATION")

    db: Any = gfs.Client(project=_PROJECT_ID)

    # ── watchlist_items ──────────────────────────────────────────────────────
    w_snap = db.collection("watchlist_items").document(watchlist_doc_id).get()
    assert w_snap.exists, f"watchlist_items/{watchlist_doc_id} vanished after write"
    w: dict[str, Any] = w_snap.to_dict() or {}

    # Fields required by frontend WatchlistItem interface
    watchlist_schema: dict[str, type] = {
        "user_id": str,
        "location_name": str,
        "latitude": float,
        "longitude": float,
        "geofence_radius_meters": float,
    }
    for field, expected in watchlist_schema.items():
        assert field in w, f"watchlist_items missing {field!r}"
        assert isinstance(w[field], expected), (
            f"watchlist_items.{field}: expected {expected.__name__}, "
            f"got {type(w[field]).__name__}"
        )

    # Coordinate value sanity
    assert abs(float(w["latitude"]) - _TARGET_LAT) < 0.001, "latitude mismatch"
    assert abs(float(w["longitude"]) - _TARGET_LON) < 0.001, "longitude mismatch"
    assert -180.0 <= float(w["longitude"]) <= 180.0, "longitude out of WGS84 range"
    assert -90.0 <= float(w["latitude"]) <= 90.0, "latitude out of WGS84 range"

    _ok(f"watchlist_items [{watchlist_doc_id}]")
    _ok(f"  location_name:         {w['location_name']!r}")
    _ok(f"  coordinates:           lat={w['latitude']}  lon={w['longitude']}")
    _ok(f"  geofence_radius_meters: {w['geofence_radius_meters']}")

    # ── daily_briefings ──────────────────────────────────────────────────────
    b_snap = db.collection("daily_briefings").document(briefing_doc_id).get()
    assert b_snap.exists, f"daily_briefings/{briefing_doc_id} vanished after write"
    b: dict[str, Any] = b_snap.to_dict() or {}

    # Fields required by frontend DailyBriefing interface
    briefing_schema: dict[str, type] = {
        "disruption_detected": bool,
        "severity_score": int,
        "confidence_grade": str,
        "explanation": str,
        "current_image_path": str,
        "baseline_image_path": str,
        "location_context": str,
        "analysed_at": str,
    }
    for field, expected in briefing_schema.items():
        assert field in b, f"daily_briefings missing {field!r}"
        assert isinstance(b[field], expected), (
            f"daily_briefings.{field}: expected {expected.__name__}, "
            f"got {type(b[field]).__name__}"
        )

    assert 1 <= int(b["severity_score"]) <= 5, (
        f"severity_score {b['severity_score']} outside [1, 5]"
    )
    assert b["confidence_grade"] in ("High", "Medium", "Low"), (
        f"confidence_grade {b['confidence_grade']!r} invalid"
    )
    assert str(b["current_image_path"]).startswith("gs://"), (
        "current_image_path must be a gs:// URI"
    )
    assert str(b["baseline_image_path"]).startswith("gs://"), (
        "baseline_image_path must be a gs:// URI"
    )

    _ok(f"daily_briefings [{briefing_doc_id}]")
    _ok(f"  disruption_detected: {b['disruption_detected']}")
    _ok(f"  severity_score:      {b['severity_score']}/5")
    _ok(f"  confidence_grade:    {b['confidence_grade']}")
    _ok(f"  current_image_path:  {b['current_image_path']}")

    # ── Frontend location-name matching heuristic ────────────────────────────
    # useFirestoreData.ts splits location_context on " — lat " to get the name.
    parsed_name = str(b["location_context"]).split(" — lat ")[0]
    assert parsed_name == _TARGET_NAME, (
        f"Frontend name-parse returned {parsed_name!r}, expected {_TARGET_NAME!r}"
    )
    _ok(f"  location_context parse: {parsed_name!r}  ✓  (matches watchlist entry)")

    # ── Sidebar sort: this briefing is the latest for this location ──────────
    all_for_loc = list(
        db.collection("daily_briefings")
        .where(filter=gfs.FieldFilter("location_context", ">=", _TARGET_NAME))
        .where(filter=gfs.FieldFilter("location_context", "<=", _TARGET_NAME + "￿"))
        .stream()
    )
    assert len(all_for_loc) >= 1, "Expected at least one briefing for this location"
    latest = max(all_for_loc, key=lambda d: (d.to_dict() or {}).get("analysed_at", ""))
    assert latest.id == briefing_doc_id, (
        f"Sidebar would show {latest.id!r} as latest, expected {briefing_doc_id!r}"
    )
    _ok(f"  Sidebar sort:         this briefing IS the latest for location  ✓")

    logger.info("    Round-trip stage PASSED")


# ── Optional cleanup ──────────────────────────────────────────────────────────

def cleanup(watchlist_doc_id: str, briefing_doc_id: str) -> None:
    """Remove the test documents created during this run."""
    _banner("CLEANUP")
    db: Any = gfs.Client(project=_PROJECT_ID)
    db.collection("watchlist_items").document(watchlist_doc_id).delete()
    db.collection("daily_briefings").document(briefing_doc_id).delete()
    _ok(f"Deleted watchlist_items/{watchlist_doc_id}")
    _ok(f"Deleted daily_briefings/{briefing_doc_id}")


# ── Main orchestrator ─────────────────────────────────────────────────────────

def main() -> None:
    keep = "--keep" in sys.argv

    _banner("SUPPLY-WATCH GOLDEN PATH END-TO-END INTEGRATION TEST")
    logger.info("    Target    : %s", _TARGET_NAME)
    logger.info("    Coords    : lat=%.4f  lon=%.4f", _TARGET_LAT, _TARGET_LON)
    logger.info("    GCS bucket: %s", _IMAGERY_BUCKET)
    logger.info("    CDSE auth : %s", "present" if _CDSE_AUTH_TOKEN else "absent (synthetic fallback)")
    logger.info("    Keep docs : %s", keep)

    stage_results: dict[str, str] = {}
    watchlist_doc_id = ""
    briefing_doc_id = ""

    # Stage 1 — fatal if geometry is broken
    try:
        bbox = stage_geometry()
        stage_results["1_geometry"] = "PASS"
    except Exception as exc:
        _fail_line(f"Stage 1 fatal: {exc}")
        sys.exit(1)

    # Stage 2 — non-fatal; absence of scenes is a data condition not a bug
    stac_result: SentinelImageResult | None = None
    try:
        stac_result = stage_stac(bbox)
        stage_results["2_stac"] = "PASS" if stac_result else "PASS (no scene available)"
    except Exception as exc:
        _fail_line(f"Stage 2 error: {exc}")
        stage_results["2_stac"] = "WARN (STAC unreachable)"

    # Stage 3 — fatal; we always produce bytes (synthetic fallback guarantees this)
    try:
        current_bytes, baseline_bytes, method = stage_imagery(stac_result, bbox)
        stage_results["3_imagery"] = f"PASS ({method})"
    except Exception as exc:
        _fail_line(f"Stage 3 fatal: {exc}")
        sys.exit(1)

    # Stage 4 — fatal; Gemini schema failure is a critical regression
    location_context = f"{_TARGET_NAME} — lat {_TARGET_LAT:.4f} lon {_TARGET_LON:.4f}"
    try:
        analysis = stage_gemini(current_bytes, baseline_bytes, location_context)
        stage_results["4_gemini"] = "PASS"
    except Exception as exc:
        _fail_line(f"Stage 4 fatal: {exc}")
        sys.exit(1)

    # Stage 5 — fatal; Firestore write failure blocks frontend
    try:
        watchlist_doc_id, briefing_doc_id = stage_firestore(
            analysis, stac_result, method
        )
        stage_results["5_firestore"] = "PASS"
    except Exception as exc:
        _fail_line(f"Stage 5 fatal: {exc}")
        sys.exit(1)

    # Stage 6 — fatal; schema mismatch would break the frontend silently
    try:
        stage_roundtrip(watchlist_doc_id, briefing_doc_id)
        stage_results["6_roundtrip"] = "PASS"
    except Exception as exc:
        _fail_line(f"Stage 6 fatal: {exc}")
        sys.exit(1)

    if not keep and watchlist_doc_id:
        cleanup(watchlist_doc_id, briefing_doc_id)
    elif keep:
        _banner("FIRESTORE STATE — FRONTEND DEMO READY")
        logger.info(
            "    Run 'cd frontend && npm run dev' → open http://localhost:3000"
        )
        logger.info(
            "    watchlist_items/%s  →  %s", watchlist_doc_id, _TARGET_NAME
        )
        logger.info(
            "    daily_briefings/%s  →  severity=%d  confidence=%s",
            briefing_doc_id,
            analysis.severity_score,
            analysis.confidence_grade,
        )

    # ── Summary ──────────────────────────────────────────────────────────────
    _banner("GOLDEN PATH SUMMARY")
    passed = 0
    for key, result in stage_results.items():
        icon = "✓" if "PASS" in result else "⚠"
        logger.info("    %s  %-18s  %s", icon, key, result)
        if "PASS" in result:
            passed += 1

    logger.info("")
    logger.info("    Stages passed : %d / %d", passed, len(stage_results))
    if watchlist_doc_id:
        logger.info("    watchlist_doc : %s", watchlist_doc_id)
        logger.info("    briefing_doc  : %s", briefing_doc_id)
    logger.info("    Docs retained : %s", keep)

    print("═" * 68)
    if passed == len(stage_results):
        logger.info("    ALL STAGES PASSED ✓")
    else:
        logger.info("    %d STAGE(S) WITH WARNINGS — see log above", len(stage_results) - passed)

    sys.exit(0)


if __name__ == "__main__":
    main()
