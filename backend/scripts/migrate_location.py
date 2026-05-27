"""
One-off migration: fix the Seagirt Marine Terminal watchlist entry.

- Renames the location to "Seagirt Marine Terminal, Port of Baltimore"
- Corrects coordinates to the waterfront pier edge (was pointing 2km inland)
- Deletes all existing daily_briefings (they used wrong coords / synthetic imagery)

Run from project root:
    GOOGLE_CLOUD_PROJECT=traveltime-465606 python3 -m backend.scripts.migrate_location
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import google.cloud.firestore as gfs

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

_PROJECT_ID = "traveltime-465606"

# Correct waterfront coordinates for Seagirt Marine Terminal container piers
_NEW_NAME = "Seagirt Marine Terminal, Port of Baltimore"
_NEW_LAT = 39.2484
_NEW_LON = -76.5494

# Old names to match against (handle both spellings)
_OLD_NAME_VARIANTS = {
    "Port of Baltimore — Seagirt Marine Terminal",
    "Seagirt Marine Terminal, Port of Baltimore",
}


def main() -> None:
    db: Any = gfs.Client(project=_PROJECT_ID)

    # ── 1. Find and update watchlist_items ──────────────────────────────────
    logger.info("Scanning watchlist_items…")
    watchlist_docs = list(db.collection("watchlist_items").stream())
    updated = 0
    target_doc_ids: list[str] = []

    for doc in watchlist_docs:
        data: dict[str, Any] = doc.to_dict() or {}
        name = str(data.get("location_name", ""))
        if name in _OLD_NAME_VARIANTS:
            old_lat = data.get("latitude")
            old_lon = data.get("longitude")
            db.collection("watchlist_items").document(doc.id).update({
                "location_name": _NEW_NAME,
                "latitude": _NEW_LAT,
                "longitude": _NEW_LON,
            })
            target_doc_ids.append(doc.id)
            updated += 1
            logger.info(
                "Updated watchlist_items/%s: '%s' → '%s'  (%.4f,%.4f) → (%.4f,%.4f)",
                doc.id, name, _NEW_NAME, old_lat, old_lon, _NEW_LAT, _NEW_LON,
            )

    if updated == 0:
        logger.warning("No matching watchlist_items found — nothing to migrate")

    # ── 2. Delete stale daily_briefings ─────────────────────────────────────
    logger.info("Scanning daily_briefings for stale entries…")
    briefings = list(db.collection("daily_briefings").stream())
    deleted = 0

    for doc in briefings:
        data = doc.to_dict() or {}
        ctx = str(data.get("location_context", ""))
        # Delete any briefing whose location_context mentions the old OR new name
        # (all existing data used wrong coords or synthetic imagery)
        should_delete = any(variant in ctx for variant in _OLD_NAME_VARIANTS) or \
                        _NEW_NAME in ctx
        if should_delete:
            db.collection("daily_briefings").document(doc.id).delete()
            deleted += 1
            logger.info("Deleted daily_briefings/%s  (%s)", doc.id, ctx[:60])

    logger.info("Migration complete — %d watchlist doc(s) updated, %d briefing(s) deleted", updated, deleted)
    logger.info("Run the backfill now:")
    logger.info(
        "  CDSE_USERNAME=tomoliveri@gmail.com CDSE_PASSWORD=<pw> "
        "GCS_BUCKET_NAME=traveltime-465606-imagery-cache "
        "GOOGLE_CLOUD_PROJECT=traveltime-465606 "
        "BACKFILL_MONTHS=12 python3 -m backend.src.main"
    )


if __name__ == "__main__":
    main()
