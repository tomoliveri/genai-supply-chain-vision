from __future__ import annotations

import io
import logging
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import google.cloud.firestore as gfs
import google.cloud.storage as gcs
import requests
from PIL import Image, ImageDraw

from backend.src.analyser import DisruptionAnalysis, analyse_disruption, analyse_disruption_from_bytes
from backend.src.external_data import (
    ExternalContext,
    build_external_context_string,
    gather_external_context,
)
from backend.src.geometry_utils import compute_aoi_bbox
from backend.src.image_processor import process_and_upload
from backend.src.stac_client import (
    SentinelImageResult,
    get_latest_sentinel_image,
    get_scenes_for_period,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

_PROJECT_ID: Final[str] = "traveltime-465606"
_WATCHLIST_COLLECTION: Final[str] = "watchlist_items"

_CDSE_TOKEN_URL: Final[str] = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(f"Required environment variable {name!r} is not set")
    return value


def _get_cdse_token() -> str | None:
    """
    Acquire a fresh CDSE OIDC bearer token via the Resource Owner Password flow.

    Reads CDSE_USERNAME and CDSE_PASSWORD from environment (injected by Cloud Run
    from Secret Manager).  Falls back gracefully to None so the pipeline can still
    run in synthetic mode if credentials are absent.
    """
    username = os.environ.get("CDSE_USERNAME")
    password = os.environ.get("CDSE_PASSWORD")
    if not username or not password:
        logger.warning("CDSE_USERNAME/CDSE_PASSWORD not set — CDSE access disabled")
        return None
    try:
        resp = requests.post(
            _CDSE_TOKEN_URL,
            data={
                "client_id": "cdse-public",
                "grant_type": "password",
                "username": username,
                "password": password,
            },
            timeout=30,
        )
        resp.raise_for_status()
        token: str = resp.json()["access_token"]
        logger.info("CDSE token acquired successfully")
        return token
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to acquire CDSE token: %s", exc)
        return None


def _find_baseline_uri(
    bucket_name: str,
    location_id: str,
    current_blob_name: str,
) -> str | None:
    """
    List all imagery blobs for *location_id*, sorted chronologically, and return
    the GCS URI of the most recent image that predates *current_blob_name*.

    Blob names are YYYY-MM-DD.jpg so lexicographic sort equals date sort.
    """
    storage_client: Any = gcs.Client()
    prefix = f"imagery_cache/{location_id}/"
    blobs: list[Any] = sorted(
        storage_client.list_blobs(bucket_name, prefix=prefix),
        key=lambda b: b.name,
        reverse=True,
    )
    for blob in blobs:
        # Skip synthetic 'baseline-*' placeholder images uploaded by
        # _upload_synthetic_images when CDSE credentials are absent.
        blob_filename = blob.name.rsplit("/", 1)[-1] if "/" in blob.name else blob.name
        if blob.name != current_blob_name and not blob_filename.startswith("baseline-"):
            return f"gs://{bucket_name}/{blob.name}"
    return None


def _make_synthetic_jpeg(seed: int, size: int = 256) -> bytes:
    rng = random.Random(seed)
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)
    for _ in range(60):
        x, y = rng.randint(0, size), rng.randint(0, size)
        r = rng.randint(4, 20)
        colour = (rng.randint(0, 60), rng.randint(40, 100), rng.randint(0, 60))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=colour)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _upload_synthetic_images(
    bucket_name: str,
    location_id: str,
    scene_date: str,
) -> tuple[str, str]:
    """Upload two synthetic JPEG images to GCS and return (current_uri, baseline_uri)."""
    storage_client: Any = gcs.Client()
    bucket = storage_client.bucket(bucket_name)

    current_blob_name = f"imagery_cache/{location_id}/{scene_date}.jpg"
    baseline_blob_name = f"imagery_cache/{location_id}/baseline-{scene_date}.jpg"

    seed = abs(hash(location_id + scene_date))
    for name, img_seed in [(current_blob_name, seed), (baseline_blob_name, seed + 1)]:
        blob = bucket.blob(name)
        if not blob.exists():
            blob.upload_from_string(_make_synthetic_jpeg(img_seed), content_type="image/jpeg")

    return (
        f"gs://{bucket_name}/{current_blob_name}",
        f"gs://{bucket_name}/{baseline_blob_name}",
    )


def _write_briefing(
    db: Any,
    analysis: DisruptionAnalysis,
    current_uri: str,
    baseline_uri: str,
    location_context: str,
    analysed_at: str,
    external_data: dict[str, Any] | None = None,
) -> str:
    """Write a daily_briefings document with all structured fields and return its ID."""
    doc: dict[str, Any] = {
        "disruption_detected": analysis.disruption_detected,
        "severity_score": analysis.severity_score,
        "confidence_grade": analysis.confidence_grade,
        "explanation": analysis.explanation,
        "current_image_path": current_uri,
        "baseline_image_path": baseline_uri,
        "location_context": location_context,
        "analysed_at": analysed_at,
        # Structured metrics for ML training
        "container_yard_fill_pct": analysis.container_yard_fill_pct,
        "vessel_count": analysis.vessel_count,
        "vessel_count_anchorage": analysis.vessel_count_anchorage,
        "disruption_category": analysis.disruption_category,
        "analysis_version": 3,  # bumped: includes geopolitical context
    }
    if external_data:
        doc["weather_summary"] = str(external_data.get("weather_summary", ""))
        doc["weather_severity"] = int(external_data.get("weather_severity", 1))
        doc["labor_status"] = str(external_data.get("labor_status", "Normal"))
        doc["peak_season_flag"] = bool(external_data.get("peak_season_flag", False))
        # Geopolitical context — new in analysis_version 3
        doc["geopolitical_active_events"] = list(external_data.get("geopolitical_active_events", []))
        doc["geopolitical_max_severity"] = int(external_data.get("geopolitical_max_severity", 1))
        doc["geopolitical_category"] = str(external_data.get("geopolitical_category", "none"))
    ref = db.collection("daily_briefings").document()
    ref.set(doc)
    return str(ref.id)


def _briefing_exists(db: Any, current_uri: str) -> bool:
    """Return True if a briefing for this exact image path already exists."""
    docs = list(
        db.collection("daily_briefings")
        .where(filter=gfs.FieldFilter("current_image_path", "==", current_uri))
        .limit(1)
        .stream()
    )
    return len(docs) > 0


def _process_scene_pair(
    doc_id: str,
    bucket_name: str,
    current_scene: SentinelImageResult,
    current_uri: str,
    baseline_uri: str,
    location_context: str,
    db: Any,
    external_data: dict[str, Any] | None = None,
) -> bool:
    """Run Gemini analysis on one current/baseline image pair and persist results."""
    if _briefing_exists(db, current_uri):
        logger.info("[%s] Briefing already exists for %s — skipping", doc_id, current_uri)
        return True

    try:
        # Build rich external context string including geopolitical signals.
        # This is the key mechanism that lets Gemini produce accurate disruption
        # assessments even when the satellite imagery alone is ambiguous — it
        # knows about armed conflicts, court rulings, insurance spikes, etc.
        ext_str = ""
        if external_data:
            # Reconstruct an ExternalContext dict from the flat external_data so
            # build_external_context_string can format it with geopolitical info.
            from backend.src.external_data import GeopoliticalContext, WeatherContext, LaborContext  # noqa: PLC0415
            from backend.src.geopolitical import GeopoliticalContext as GC  # noqa: PLC0415

            recon: ExternalContext = ExternalContext(
                weather=WeatherContext(
                    summary=str(external_data.get("weather_summary", "")),
                    severity=int(external_data.get("weather_severity", 1)),
                    code="unknown",
                ),
                labor=LaborContext(
                    status=str(external_data.get("labor_status", "Normal")),
                    detail="",
                ),
                peak_season=bool(external_data.get("peak_season_flag", False)),
                geopolitical=GC(
                    active_events=list(external_data.get("geopolitical_active_events", [])),
                    max_severity=int(external_data.get("geopolitical_max_severity", 1)),
                    category=str(external_data.get("geopolitical_category", "none")),
                    summary="",
                    impacts=[],
                ),
            )
            ext_str = build_external_context_string(recon)

        # Fetch bytes directly and use the non-Firestore-writing path to avoid
        # the double-write bug: analyse_disruption() writes internally, and
        # _write_briefing() would be the second write.  analyse_disruption_from_bytes()
        # calls Gemini but does NOT persist.
        storage: Any = gcs.Client()
        current_bytes = storage.bucket(bucket_name).blob(
            current_uri.removeprefix(f"gs://{bucket_name}/")
        ).download_as_bytes()
        baseline_bytes = storage.bucket(bucket_name).blob(
            baseline_uri.removeprefix(f"gs://{bucket_name}/")
        ).download_as_bytes()
        analysis = analyse_disruption_from_bytes(
            current_bytes=current_bytes,
            baseline_bytes=baseline_bytes,
            location_context=location_context,
            external_context_str=ext_str,
        )
        analysed_at = current_scene["capture_date"]
        _write_briefing(db, analysis, current_uri, baseline_uri, location_context, analysed_at, external_data)
        logger.info(
            "[%s] Briefing written — scene=%s  disruption=%s  severity=%d",
            doc_id,
            current_scene["capture_date"][:10],
            analysis.disruption_detected,
            analysis.severity_score,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] Gemini analysis failed: %s", doc_id, exc)
        return False


def _backfill_location(
    doc_id: str,
    data: dict[str, Any],
    bucket_name: str,
    auth_token: str,
    months_back: int = 12,
) -> int:
    """
    Download and analyse historical Sentinel-2 scenes for one watchlist location.

    Fetches the best (lowest cloud cover) scene per calendar month going back
    *months_back* months, uploads each to GCS, then writes one daily_briefing
    per consecutive pair.  Already-uploaded images are skipped so the function
    is safely re-entrant.

    Returns the number of briefings written.
    """
    location_name: str = str(data.get("location_name", doc_id))
    latitude = float(data["latitude"])
    longitude = float(data["longitude"])
    half_side = float(data.get("aoi_half_side_m", 1000.0))
    bbox = compute_aoi_bbox(latitude, longitude, half_side)
    location_context = f"{location_name} — lat {latitude:.4f} lon {longitude:.4f}"

    end_date = datetime.now(tz=timezone.utc)
    start_date = end_date - timedelta(days=months_back * 31)

    logger.info(
        "[%s] Backfill: querying %d months (%s → %s)",
        doc_id, months_back,
        start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"),
    )

    scenes = get_scenes_for_period(bbox, start_date, end_date, max_cloud_cover=15.0)
    if not scenes:
        logger.warning("[%s] No scenes found for backfill period", doc_id)
        return 0

    logger.info("[%s] %d scene(s) to process for backfill", doc_id, len(scenes))

    storage_client: Any = gcs.Client()

    # Upload all scenes first so consecutive pairs are available for analysis.
    uploaded: list[tuple[SentinelImageResult, str]] = []
    for scene in scenes:
        tci = scene.get("tci")
        tci_url = tci["https"] if tci else None
        if not tci_url:
            logger.warning("[%s] Scene %s has no TCI URL — skipping", doc_id, scene["product_id"][:20])
            continue

        scene_date = scene["capture_date"][:10]
        expected_blob = f"imagery_cache/{doc_id}/{scene_date}.jpg"
        blob = storage_client.bucket(bucket_name).blob(expected_blob)
        if blob.exists():
            logger.info("[%s] %s already uploaded — reusing", doc_id, scene_date)
            uploaded.append((scene, f"gs://{bucket_name}/{expected_blob}"))
            continue

        try:
            uri = process_and_upload(
                image_result=scene,
                bbox_wgs84=bbox,
                location_id=doc_id,
                bucket_name=bucket_name,
                auth_token=auth_token,
            )
            uploaded.append((scene, uri))
            logger.info("[%s] Uploaded %s → %s", doc_id, scene_date, uri)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] Upload failed for %s: %s", doc_id, scene_date, exc)

    if len(uploaded) < 2:
        logger.warning("[%s] Need ≥2 uploaded scenes for comparison — got %d", doc_id, len(uploaded))
        return 0

    db: Any = gfs.Client(project=_PROJECT_ID)
    briefings_written = 0
    for i in range(1, len(uploaded)):
        baseline_scene, baseline_uri = uploaded[i - 1]
        current_scene, current_uri = uploaded[i]

        # Gather ALL external context — weather, labour, peak season, AND geopolitical.
        ext_ctx = gather_external_context(
            location_name, latitude, longitude,
            current_scene["capture_date"],
        )
        ext_data: dict[str, Any] = {
            "weather_summary": ext_ctx["weather"]["summary"],
            "weather_severity": ext_ctx["weather"]["severity"],
            "labor_status": ext_ctx["labor"]["status"],
            "peak_season_flag": ext_ctx["peak_season"],
            # Geopolitical context — new in analysis_version 3
            "geopolitical_active_events": ext_ctx["geopolitical"]["active_events"],
            "geopolitical_max_severity": ext_ctx["geopolitical"]["max_severity"],
            "geopolitical_category": ext_ctx["geopolitical"]["category"],
        }

        if _process_scene_pair(doc_id, bucket_name, current_scene, current_uri, baseline_uri, location_context, db, ext_data):
            briefings_written += 1

    logger.info("[%s] Backfill complete — %d briefing(s) written", doc_id, briefings_written)
    return briefings_written


def _process_item(
    doc_id: str,
    data: dict[str, Any],
    bucket_name: str,
    auth_token: str | None,
) -> bool:
    """
    Run the daily pipeline for one watchlist item (latest scene only).
    Returns True on success, False on any non-fatal failure.
    """
    location_name: str = str(data.get("location_name", doc_id))
    try:
        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
    except (KeyError, TypeError, ValueError) as exc:
        logger.error("[%s] Invalid coordinates in document: %s", doc_id, exc)
        return False

    logger.info(
        "[%s] Daily run — %r  lat=%.4f  lon=%.4f",
        doc_id, location_name, latitude, longitude,
    )

    try:
        half_side = float(data.get("aoi_half_side_m", 1000.0))
        bbox = compute_aoi_bbox(latitude, longitude, half_side)
        image_result = get_latest_sentinel_image(bbox)
        if image_result is None:
            logger.warning("[%s] No qualifying Sentinel-2 image found — skipping", doc_id)
            return False

        logger.info(
            "[%s] Found scene %s  cloud=%.1f%%",
            doc_id, image_result["product_id"], image_result["cloud_cover"],
        )

        scene_date = image_result["capture_date"][:10]
        location_context = f"{location_name} — lat {latitude:.4f} lon {longitude:.4f}"
        db: Any = gfs.Client(project=_PROJECT_ID)

        if auth_token:
            current_uri = process_and_upload(
                image_result=image_result,
                bbox_wgs84=bbox,
                location_id=doc_id,
                bucket_name=bucket_name,
                auth_token=auth_token,
            )
            current_blob_name = current_uri.removeprefix(f"gs://{bucket_name}/")
            logger.info("[%s] Current image uploaded: %s", doc_id, current_uri)
            baseline_uri = _find_baseline_uri(bucket_name, doc_id, current_blob_name)
            if baseline_uri is None:
                logger.info("[%s] No baseline yet — skipping analysis", doc_id)
                return True

            ext_ctx = gather_external_context(location_name, latitude, longitude, scene_date)
            ext_data: dict[str, Any] = {
                "weather_summary": ext_ctx["weather"]["summary"],
                "weather_severity": ext_ctx["weather"]["severity"],
                "labor_status": ext_ctx["labor"]["status"],
                "peak_season_flag": ext_ctx["peak_season"],
                "geopolitical_active_events": ext_ctx["geopolitical"]["active_events"],
                "geopolitical_max_severity": ext_ctx["geopolitical"]["max_severity"],
                "geopolitical_category": ext_ctx["geopolitical"]["category"],
            }

            _process_scene_pair(
                doc_id, bucket_name, image_result,
                current_uri, baseline_uri, location_context, db, ext_data,
            )
        else:
            logger.warning(
                "[%s] No CDSE credentials — using synthetic imagery for Gemini analysis",
                doc_id,
            )
            current_uri, baseline_uri = _upload_synthetic_images(bucket_name, doc_id, scene_date)

            storage_client: Any = gcs.Client()
            current_bytes = storage_client.bucket(bucket_name).blob(
                current_uri.removeprefix(f"gs://{bucket_name}/")
            ).download_as_bytes()
            baseline_bytes = storage_client.bucket(bucket_name).blob(
                baseline_uri.removeprefix(f"gs://{bucket_name}/")
            ).download_as_bytes()
            analysis: DisruptionAnalysis = analyse_disruption_from_bytes(
                current_bytes=current_bytes,
                baseline_bytes=baseline_bytes,
                location_context=location_context,
            )
            _write_briefing(
                db, analysis, current_uri, baseline_uri,
                location_context, datetime.now(tz=timezone.utc).isoformat(),
            )

        return True

    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] Pipeline error: %s", doc_id, exc)
        return False


def main() -> None:
    bucket_name = _require_env("GCS_BUCKET_NAME")

    # Prefer auto-refreshed credentials over a static token env var.
    auth_token: str | None = _get_cdse_token() or os.environ.get("CDSE_AUTH_TOKEN") or None

    backfill_months = int(os.environ.get("BACKFILL_MONTHS", "0"))

    logger.info("Supply-chain vision pipeline starting")
    if auth_token:
        logger.info("CDSE authentication: OK")
    else:
        logger.warning("CDSE authentication: unavailable — synthetic imagery will be used")

    db: Any = gfs.Client(project=_PROJECT_ID)
    docs: list[Any] = list(db.collection(_WATCHLIST_COLLECTION).stream())

    if not docs:
        logger.info("Watchlist is empty — nothing to process")
        sys.exit(0)

    logger.info("Processing %d watchlist item(s)", len(docs))

    successes = 0
    failures = 0

    for doc in docs:
        raw: dict[str, Any] = doc.to_dict() or {}

        if backfill_months > 0 and auth_token:
            try:
                written = _backfill_location(doc.id, raw, bucket_name, auth_token, backfill_months)
                logger.info("[%s] Backfill wrote %d briefing(s)", doc.id, written)
                successes += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("[%s] Backfill error: %s", doc.id, exc)
                failures += 1
        else:
            if _process_item(doc.id, raw, bucket_name, auth_token):
                successes += 1
            else:
                failures += 1

    logger.info(
        "Run complete — %d ok  %d failed  %d total",
        successes, failures, len(docs),
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
