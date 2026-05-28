"""
One-shot (but re-entrant) script to populate the Firestore watchlist_items
collection with all global ports currently monitored by SupplyWatch.

Ports are grouped by region and each includes real-world coordinates at the
waterfront container terminal edge (not the administrative centre).

Usage:
    python -m backend.scripts.ingest_ports [--reset] [--dry-run]

    --reset   : Delete existing watchlist_items before adding (default: upsert by name)
    --dry-run : Print what would be added without touching Firestore

After ingestion, run the backfill:
    CDSE_USERNAME='...' CDSE_PASSWORD='...' \\
    GCS_BUCKET_NAME='traveltime-465606-imagery-cache' \\
    GOOGLE_CLOUD_PROJECT='traveltime-465606' \\
    BACKFILL_MONTHS=12 \\
    python3 -m backend.src.main
"""

from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

import google.cloud.firestore as gfs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

_PROJECT_ID: str = "traveltime-465606"
_COLLECTION: str = "watchlist_items"

# ── Port definitions ─────────────────────────────────────────────────────────
# Each entry: (location_name, latitude, longitude, aoi_half_side_m, geofence_radius_m)
#
# Coordinates are verified to be at the waterfront container terminal edge.
# aoi_half_side_m is the half-side of the square AOI — larger values for
# sprawling ports (Jebel Ali, Rotterdam, LA/LB).

PORTS: list[dict[str, Any]] = [
    # ── Middle East / Persian Gulf ──────────────────────────────────────────
    {
        "location_name": "Port of Jebel Ali, Dubai",
        "latitude": 25.0110,
        "longitude": 55.0611,
        "aoi_half_side_m": 4000.0,  # Massive terminal complex
        "geofence_radius_meters": 5000.0,
    },
    {
        "location_name": "Port of Salalah, Oman",
        "latitude": 16.9438,
        "longitude": 54.0085,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Jeddah Islamic Port, Saudi Arabia",
        "latitude": 21.4858,
        "longitude": 39.1560,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },

    # ── Panama (Central America) ────────────────────────────────────────────
    {
        "location_name": "Port of Balboa, Panama",
        "latitude": 8.9655,
        "longitude": -79.5602,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Cristobal, Panama",
        "latitude": 9.3512,
        "longitude": -79.9037,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },

    # ── Africa ──────────────────────────────────────────────────────────────
    {
        "location_name": "Port of Casablanca, Morocco",
        "latitude": 33.6053,
        "longitude": -7.6198,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Mombasa, Kenya",
        "latitude": -4.0528,
        "longitude": 39.6682,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Tema, Ghana",
        "latitude": 5.6290,
        "longitude": -0.0223,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Beira, Mozambique",
        "latitude": -19.8230,
        "longitude": 34.8381,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Cape Town, South Africa",
        "latitude": -33.9090,
        "longitude": 18.4233,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Durban, South Africa",
        "latitude": -29.8730,
        "longitude": 31.0407,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },

    # ── Caribbean ───────────────────────────────────────────────────────────
    {
        "location_name": "Port of Kingston, Jamaica",
        "latitude": 17.9785,
        "longitude": -76.8089,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },

    # ── Europe ──────────────────────────────────────────────────────────────
    {
        "location_name": "Port of Rotterdam, Netherlands",
        "latitude": 51.9493,
        "longitude": 4.1434,
        "aoi_half_side_m": 4000.0,  # Sprawling Maasvlakte terminals
        "geofence_radius_meters": 5000.0,
    },
    {
        "location_name": "Port of Hamburg, Germany",
        "latitude": 53.5432,
        "longitude": 9.9660,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Bremerhaven, Germany",
        "latitude": 53.5644,
        "longitude": 8.5544,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Wilhelmshaven, Germany",
        "latitude": 53.5967,
        "longitude": 8.1448,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Lisbon, Portugal",
        "latitude": 38.7036,
        "longitude": -9.1728,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Piraeus, Greece",
        "latitude": 37.9420,
        "longitude": 23.6400,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Genoa, Italy",
        "latitude": 44.4087,
        "longitude": 8.9197,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Gioia Tauro, Italy",
        "latitude": 38.4375,
        "longitude": 15.9050,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Antwerp-Bruges, Belgium",
        "latitude": 51.3200,
        "longitude": 4.3042,
        "aoi_half_side_m": 4000.0,
        "geofence_radius_meters": 5000.0,
    },
    {
        "location_name": "Port of Felixstowe, United Kingdom",
        "latitude": 51.9589,
        "longitude": 1.3165,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Valencia, Spain",
        "latitude": 39.4435,
        "longitude": -0.3236,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Algeciras, Spain",
        "latitude": 36.1342,
        "longitude": -5.4313,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Barcelona, Spain",
        "latitude": 41.3357,
        "longitude": 2.1668,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Le Havre, France",
        "latitude": 49.4760,
        "longitude": 0.1372,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Marseille-Fos, France",
        "latitude": 43.3524,
        "longitude": 5.3223,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Ambarli, Istanbul, Turkey",
        "latitude": 41.0027,
        "longitude": 28.6750,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },

    # ── East Asia ───────────────────────────────────────────────────────────
    {
        "location_name": "Port of Ningbo-Zhoushan, China",
        "latitude": 29.9337,
        "longitude": 121.8656,
        "aoi_half_side_m": 4000.0,
        "geofence_radius_meters": 5000.0,
    },

    # ── Southeast Asia ──────────────────────────────────────────────────────
    {
        "location_name": "Port of Tanjung Priok, Jakarta, Indonesia",
        "latitude": -6.1137,
        "longitude": 106.8816,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Surabaya, Indonesia",
        "latitude": -7.2504,
        "longitude": 112.7437,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Singapore",
        "latitude": 1.2574,
        "longitude": 103.8195,
        "aoi_half_side_m": 4000.0,
        "geofence_radius_meters": 5000.0,
    },
    {
        "location_name": "Port Klang, Malaysia",
        "latitude": 2.9994,
        "longitude": 101.3957,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Tanjung Pelepas, Malaysia",
        "latitude": 1.3670,
        "longitude": 103.5538,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Laem Chabang, Thailand",
        "latitude": 13.0707,
        "longitude": 100.8912,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Ho Chi Minh City, Vietnam",
        "latitude": 10.6563,
        "longitude": 106.7856,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Manila, Philippines",
        "latitude": 14.5876,
        "longitude": 120.9520,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },

    # ── East Asia ───────────────────────────────────────────────────────────
    {
        "location_name": "Port of Shanghai, China",
        "latitude": 31.3794,
        "longitude": 121.7047,
        "aoi_half_side_m": 4000.0,  # World's busiest — Yangshan Deep Water Port
        "geofence_radius_meters": 5000.0,
    },
    {
        "location_name": "Port of Shenzhen (Yantian), China",
        "latitude": 22.5606,
        "longitude": 114.2806,
        "aoi_half_side_m": 4000.0,
        "geofence_radius_meters": 5000.0,
    },
    {
        "location_name": "Port of Guangzhou (Nansha), China",
        "latitude": 22.6592,
        "longitude": 113.6530,
        "aoi_half_side_m": 4000.0,
        "geofence_radius_meters": 5000.0,
    },
    {
        "location_name": "Port of Qingdao, China",
        "latitude": 36.0812,
        "longitude": 120.3143,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Tianjin, China",
        "latitude": 38.9851,
        "longitude": 117.7913,
        "aoi_half_side_m": 4000.0,
        "geofence_radius_meters": 5000.0,
    },
    {
        "location_name": "Port of Xiamen, China",
        "latitude": 24.4577,
        "longitude": 118.0857,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Hong Kong",
        "latitude": 22.3396,
        "longitude": 114.1349,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Kaohsiung, Taiwan",
        "latitude": 22.5506,
        "longitude": 120.3217,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },

    # ── Northeast Asia ──────────────────────────────────────────────────────
    {
        "location_name": "Port of Busan, South Korea",
        "latitude": 35.1012,
        "longitude": 129.0679,
        "aoi_half_side_m": 4000.0,
        "geofence_radius_meters": 5000.0,
    },
    {
        "location_name": "Port of Tokyo, Japan",
        "latitude": 35.6169,
        "longitude": 139.7961,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },

    # ── South Asia ──────────────────────────────────────────────────────────
    {
        "location_name": "Port of Colombo, Sri Lanka",
        "latitude": 6.9533,
        "longitude": 79.8459,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Nhava Sheva (JNPT), Mumbai, India",
        "latitude": 18.9497,
        "longitude": 72.9447,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Mundra, India",
        "latitude": 22.7475,
        "longitude": 69.7048,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },

    # ── South America ───────────────────────────────────────────────────────
    {
        "location_name": "Port of San Antonio, Chile",
        "latitude": -33.5857,
        "longitude": -71.6131,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Santos, Brazil",
        "latitude": -23.9618,
        "longitude": -46.3043,
        "aoi_half_side_m": 4000.0,
        "geofence_radius_meters": 5000.0,
    },

    # ── North America ───────────────────────────────────────────────────────
    {
        "location_name": "Port of Los Angeles, California",
        "latitude": 33.7361,
        "longitude": -118.2732,
        "aoi_half_side_m": 4000.0,
        "geofence_radius_meters": 5000.0,
    },
    {
        "location_name": "Port of Long Beach, California",
        "latitude": 33.7564,
        "longitude": -118.1850,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of New York and New Jersey",
        "latitude": 40.6686,
        "longitude": -74.0695,
        "aoi_half_side_m": 4000.0,
        "geofence_radius_meters": 5000.0,
    },
    {
        "location_name": "Port of Savannah, Georgia",
        "latitude": 32.0793,
        "longitude": -81.0883,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Charleston, South Carolina",
        "latitude": 32.7819,
        "longitude": -79.9221,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Norfolk, Virginia",
        "latitude": 36.9227,
        "longitude": -76.3459,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Houston, Texas",
        "latitude": 29.7215,
        "longitude": -95.0229,
        "aoi_half_side_m": 4000.0,
        "geofence_radius_meters": 5000.0,
    },
    {
        "location_name": "Seagirt Marine Terminal, Port of Baltimore",
        "latitude": 39.2484,
        "longitude": -76.5494,
        "aoi_half_side_m": 1000.0,
        "geofence_radius_meters": 2000.0,
    },
    {
        "location_name": "Port of Vancouver, Canada",
        "latitude": 49.2942,
        "longitude": -123.0806,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },

    # ── Oceania ─────────────────────────────────────────────────────────────
    {
        "location_name": "Port of Tauranga, New Zealand",
        "latitude": -37.6617,
        "longitude": 176.1727,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Lyttelton, New Zealand",
        "latitude": -43.6062,
        "longitude": 172.7234,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },

    # ── Australia ───────────────────────────────────────────────────────────
    {
        "location_name": "Port of Melbourne, Australia",
        "latitude": -37.8475,
        "longitude": 144.9165,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port Botany, Sydney, Australia",
        "latitude": -33.9696,
        "longitude": 151.2007,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Brisbane, Australia",
        "latitude": -27.3860,
        "longitude": 153.1575,
        "aoi_half_side_m": 3000.0,
        "geofence_radius_meters": 4000.0,
    },
    {
        "location_name": "Port of Fremantle, Australia",
        "latitude": -32.0473,
        "longitude": 115.7462,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
    {
        "location_name": "Port of Adelaide, Australia",
        "latitude": -34.7795,
        "longitude": 138.4991,
        "aoi_half_side_m": 2000.0,
        "geofence_radius_meters": 3000.0,
    },
]


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    reset = "--reset" in sys.argv

    logger.info("SupplyWatch port ingestion")
    logger.info("  Ports defined: %d", len(PORTS))
    logger.info("  Reset: %s", reset)
    logger.info("  Dry run: %s", dry_run)

    if dry_run:
        logger.info("\nWould add the following ports:")
        for port in PORTS:
            logger.info(
                "  %s  (%.4f, %.4f)  AOI=%dm",
                port["location_name"],
                port["latitude"],
                port["longitude"],
                port["aoi_half_side_m"],
            )
        logger.info("\nDry run complete — no changes made. Remove --dry-run to apply.")
        return

    db: Any = gfs.Client(project=_PROJECT_ID)

    # Optionally clear existing entries
    if reset:
        existing_docs = list(db.collection(_COLLECTION).stream())
        if existing_docs:
            logger.info("Resetting: deleting %d existing watchlist_items...", len(existing_docs))
            batch = db.batch()
            for doc in existing_docs:
                batch.delete(doc.reference)
            batch.commit()
            logger.info("  Deleted %d document(s)", len(existing_docs))

    added = 0
    skipped = 0

    for port in PORTS:
        # Check if this port name already exists
        existing = list(
            db.collection(_COLLECTION)
            .where(filter=gfs.FieldFilter("location_name", "==", port["location_name"]))
            .limit(1)
            .stream()
        )

        if existing:
            # Update coordinates and AOI size in case they changed
            doc_ref = existing[0].reference
            doc_ref.update({
                "latitude": port["latitude"],
                "longitude": port["longitude"],
                "aoi_half_side_m": port["aoi_half_side_m"],
                "geofence_radius_meters": port["geofence_radius_meters"],
            })
            logger.info("  UPDATED  %s  (id=%s)", port["location_name"], existing[0].id)
            skipped += 1
        else:
            doc_id = str(uuid.uuid4())
            db.collection(_COLLECTION).document(doc_id).set({
                "user_id": "supplywatch-system",
                "location_name": port["location_name"],
                "latitude": port["latitude"],
                "longitude": port["longitude"],
                "aoi_half_side_m": port["aoi_half_side_m"],
                "geofence_radius_meters": port["geofence_radius_meters"],
                "created_at": datetime.now(tz=timezone.utc),
            })
            logger.info("  ADDED    %s  (id=%s)", port["location_name"], doc_id)
            added += 1

    logger.info(
        "\nIngestion complete — %d added, %d updated, %d total ports",
        added, skipped, len(PORTS),
    )


if __name__ == "__main__":
    main()
