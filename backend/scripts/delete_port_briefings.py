"""
Delete existing daily_briefings for specified ports so the backfill can
regenerate them with the updated analysis_version=4 prompt.

Usage:
    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
    python backend/scripts/delete_port_briefings.py [--dry-run]

Without --dry-run, deletes matching briefings from Firestore.
With --dry-run, prints what would be deleted.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import google.cloud.firestore as gfs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

_PROJECT_ID: str = "traveltime-465606"
_BRIEFINGS_COLLECTION: str = "daily_briefings"

# Ports to regenerate — these location_names must match exactly what's in
# the location_context field of daily_briefings documents.
REGENERATE_PORTS: list[str] = [
    # Specifically requested
    "Port of Beira, Mozambique",
    "Port of Balboa, Panama",
    "Port of Cristobal, Panama",
    "Port of Jebel Ali, Dubai",
    "Port of Salalah, Oman",
    "Port of Casablanca, Morocco",
    # Australian ports
    "Port of Melbourne, Australia",
    "Port Botany, Sydney, Australia",
    "Port of Brisbane, Australia",
    "Port of Fremantle, Australia",
    "Port of Adelaide, Australia",
]


def _location_name_from_context(context: str) -> str:
    """Extract location_name from a location_context string."""
    return context.split(" — lat ")[0]


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    logger.info("Deleting briefings for %d ports", len(REGENERATE_PORTS))
    for port in REGENERATE_PORTS:
        logger.info("  - %s", port)

    db: Any = gfs.Client(project=_PROJECT_ID)
    briefings_ref = db.collection(_BRIEFINGS_COLLECTION)

    total_deleted = 0
    total_checked = 0

    for port_name in REGENERATE_PORTS:
        # Firestore doesn't support prefix queries natively, so we fetch all
        # briefings and filter client-side.  At ~70 ports × ~12 months this is
        # a few hundred documents — well within Firestore limits.
        docs = list(briefings_ref.stream())
        matching = [
            doc for doc in docs
            if _location_name_from_context(doc.to_dict().get("location_context", "")) == port_name
        ]

        logger.info(
            "%s: %d briefing(s) found (analysis_version=%s)",
            port_name,
            len(matching),
            ", ".join(
                str(doc.to_dict().get("analysis_version", "?"))
                for doc in matching
            ) if matching else "N/A",
        )

        if dry_run:
            for doc in matching:
                data = doc.to_dict()
                logger.info(
                    "  WOULD DELETE: %s  version=%s  analysed_at=%s",
                    doc.id,
                    data.get("analysis_version"),
                    data.get("analysed_at", "")[:10],
                )
        else:
            for doc in matching:
                doc.reference.delete()
                logger.info("  DELETED: %s", doc.id)
                total_deleted += 1

        total_checked += len(matching)

    if dry_run:
        logger.info(
            "\nDry run complete — %d briefing(s) would be deleted across %d port(s). "
            "Remove --dry-run to apply.",
            total_checked,
            len(REGENERATE_PORTS),
        )
    else:
        logger.info(
            "\nDone — %d briefing(s) deleted across %d port(s).",
            total_deleted,
            len(REGENERATE_PORTS),
        )


if __name__ == "__main__":
    main()
