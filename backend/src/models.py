from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TypedDict


class FirestoreWatchlistItem(TypedDict):
    """
    Firestore document shape for the ``watchlist_items`` collection.

    Collection path: ``watchlist_items/{item_id}``

    Field types in Firestore:
        user_id                 → string
        location_name           → string
        latitude                → number  (WGS84, decimal degrees)
        longitude               → number  (WGS84, decimal degrees)
        geofence_radius_meters  → number  (metres, > 0)
        aoi_half_side_m         → number  (metres; half-side of square AOI, default 1 000)
        created_at              → timestamp
    """

    user_id: str
    location_name: str
    latitude: float
    longitude: float
    geofence_radius_meters: float
    aoi_half_side_m: float
    created_at: datetime


@dataclass(frozen=True)
class Coordinates:
    """WGS84 coordinate pair. Axis convention: (latitude, longitude) — (y, x)."""

    latitude: float
    longitude: float


@dataclass
class WatchlistItem:
    """
    In-memory representation of a ``watchlist_items`` Firestore document.

    Use :meth:`create` as the primary constructor so that ``item_id`` and
    ``created_at`` are always populated correctly.
    """

    user_id: str
    location_name: str
    coordinates: Coordinates
    geofence_radius_meters: float
    created_at: datetime
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def create(
        cls,
        user_id: str,
        location_name: str,
        latitude: float,
        longitude: float,
        geofence_radius_meters: float,
    ) -> WatchlistItem:
        return cls(
            user_id=user_id,
            location_name=location_name,
            coordinates=Coordinates(latitude=latitude, longitude=longitude),
            geofence_radius_meters=geofence_radius_meters,
            created_at=datetime.now(tz=timezone.utc),
        )

    def to_firestore_dict(self) -> FirestoreWatchlistItem:
        """Return a flat dict ready for a Firestore ``set`` / ``update`` call."""
        return FirestoreWatchlistItem(
            user_id=self.user_id,
            location_name=self.location_name,
            latitude=self.coordinates.latitude,
            longitude=self.coordinates.longitude,
            geofence_radius_meters=self.geofence_radius_meters,
            created_at=self.created_at,
        )
