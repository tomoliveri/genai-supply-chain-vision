"""
One-shot script to delete stale duplicate daily_briefings documents that were
created by the old double-write bug (where analyse_disruption() wrote to
Firestore internally AND _write_briefing() wrote a second copy).

A document is considered a stale duplicate when:
- Multiple briefings exist for the same (location_context, current_image_path) pair
- The one with the later (more recent) analysed_at is kept; older ones deleted.

Usage:
    python -m backend.scripts.cleanup_duplicate_briefings [--dry-run]

Pass --dry-run to report without deleting.
"""

from __future__ import annotations

import logging
import sys
from collections import defaultdict
from typing import Any

import google.cloud.firestore as gfs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

_PROJECT_ID: str = "traveltime-465606"


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    db: Any = gfs.Client(project=_PROJECT_ID)

    # Fetch all briefings
    briefings: list[tuple[str, dict[str, Any]]] = []
    for doc in db.collection("daily_briefings").stream():
        data: dict[str, Any] = doc.to_dict() or {}
        briefings.append((doc.id, data))

    logger.info("Loaded %d briefings from Firestore", len(briefings))

    # Group by (location_context, current_image_path) to find duplicates
    groups: dict[tuple[str, str], list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for doc_id, data in briefings:
        key = (str(data.get("location_context", "")), str(data.get("current_image_path", "")))
        groups[key].append((doc_id, data))

    duplicates_to_delete: list[str] = []

    for key, items in groups.items():
        if len(items) <= 1:
            continue

        # Sort by analysed_at, newest first
        items.sort(
            key=lambda x: str(x[1].get("analysed_at", "")),
            reverse=True,
        )

        keeper = items[0]
        stale = items[1:]

        logger.info(
            "Duplicate group: location=%r  image=%s",
            key[0][:60],
            key[1].rsplit("/", 1)[-1] if "/" in key[1] else key[1],
        )
        logger.info(
            "  KEEP  %s  analysed_at=%s  severity=%d  analysis_version=%s",
            keeper[0],
            keeper[1].get("analysed_at", "")[:19],
            keeper[1].get("severity_score", 0),
            keeper[1].get("analysis_version", "N/A"),
        )

        for doc_id, data in stale:
            logger.info(
                "  DEL   %s  analysed_at=%s  severity=%d  analysis_version=%s",
                doc_id,
                data.get("analysed_at", "")[:19],
                data.get("severity_score", 0),
                data.get("analysis_version", "N/A"),
            )
            duplicates_to_delete.append(doc_id)

    if not duplicates_to_delete:
        logger.info("No duplicate briefings found — nothing to clean up")
        return

    logger.info(
        "\nFound %d stale duplicate(s) across %d group(s)",
        len(duplicates_to_delete),
        sum(1 for items in groups.values() if len(items) > 1),
    )

    if dry_run:
        logger.info("DRY RUN — no documents deleted. Remove --dry-run to execute.")
        return

    # Batch delete
    batch = db.batch()
    for doc_id in duplicates_to_delete:
        batch.delete(db.collection("daily_briefings").document(doc_id))

    batch.commit()
    logger.info("Deleted %d stale duplicate briefings", len(duplicates_to_delete))


if __name__ == "__main__":
    main()
